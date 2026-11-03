"""Matched recorded starts; scratch-only palm friction/arm cap/mass interventions."""
import os,sys,json,time,zipfile,argparse
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
ROOT=Path('/workspace/mimickit_trial');OUT=ROOT/'crawl-traction-20261102'
sys.path[:0]=[str(OUT/'pipeline'),str(ROOT/'MimicKit/mimickit'),str(OUT/'assets/MimicKitTransfer')]
import numpy as np,torch,warp as wp,yaml
from slow_loco_disabled import DisabledSlowLocoEnv
from omni_policy import OmniPPOAgent
from learning.base_agent import AgentMode
from util import mp_util

@wp.kernel
def grip(n:wp.array(dtype=int), ids:wp.array2d(dtype=int), geom:wp.array(dtype=wp.vec2i),
         body:wp.array(dtype=int), mu:wp.array2d(dtype=float), factors:wp.array(dtype=float)):
    w,c=wp.tid()
    if c<n[w]:
        pair=geom[ids[w,c]];a=body[pair[0]];b=body[pair[1]]
        if (a==0 and (b==6 or b==9)) or (b==0 and (a==6 or a==9)):
            mu[w,c]*=factors[w]

from sequential_contact_gpu import ContactProblem
@wp.kernel
def measure(p:ContactProblem, counter:wp.array(dtype=int), geom:wp.array(dtype=wp.vec2i),
            frames:wp.array(dtype=wp.mat33), bodies:wp.array(dtype=int),
            forces:wp.array4d(dtype=float), slip:wp.array3d(dtype=float),
            torque:wp.array3d(dtype=float), mu:wp.array3d(dtype=float)):
    w=wp.tid();s=counter[0]
    for j in range(p.nmotor):torque[s,w,j]=p.motor_impulse[w,j]/p.dt[0]
    for c in range(p.ncontact[w]):
        ident=p.manifold.contact_ids[w,c];pair=geom[ident]
        a=bodies[pair[0]];b=bodies[pair[1]]
        if a!=0 and b!=0:continue
        f=frames[ident][0]*p.contact_impulse[w,c,0]/p.dt[0]
        g=p.manifold.group[w,c]
        if g>=0:f+=(p.manifold.frame[w,g][1]*p.contact_impulse[w,c,1]+p.manifold.frame[w,g][2]*p.contact_impulse[w,c,2])/p.dt[0]
        for side in range(2):
            body=bodies[pair[side]]
            if body>0:
                for k in range(3):forces[s,w,body-1,k]+=float(2*side-1)*f[k]
        if (a==6 or b==6 or a==9 or b==9) and g>=0 and ident==p.manifold.first[w,g]:
            h=int(0)
            if a==9 or b==9:h=1
            vx=float(0.);vy=float(0.)
            for j in range(p.nv):
                vx+=p.manifold.J[w,g,0,j]*p.velocity[w,j]
                vy+=p.manifold.J[w,g,1,j]*p.velocity[w,j]
            slip[s,w,h]=wp.sqrt(vx*vx+vy*vy)
            mu[s,w,h]=p.friction[w,c]

@wp.kernel
def count(counter:wp.array(dtype=int)):counter[0]+=1

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mass',type=float,default=1.);ap.add_argument('--ticks',type=int,default=300);ap.add_argument('--controller',default='policy',choices=['policy','pull']);ap.add_argument('--wide',action='store_true');args=ap.parse_args()
    torch.set_num_threads(2);torch.set_num_interop_threads(1);torch.manual_seed(20261102)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6795);os.chdir(ROOT/'MimicKit')
    cases=[dict(grip=g,arm=a) for g,a in [(1,1),(1.1,1),(1.25,1),(1.5,1),(2,1),(1,1.25),(1,1.5),(1.25,1.25)]]
    if args.wide:cases=[dict(grip=g,arm=a) for g,a in [(1,1),(2,1),(3,1),(4,1),(2,1.25),(3,1.25),(4,1.25),(3,1.5)]]
    S=8 if args.controller=='policy' else 4;N=S*len(cases);tag='mass'+str(args.mass).replace('.','p');dest=OUT/(tag+('' if args.controller=='policy' else '_pull')+('_wide' if args.wide else ''));dest.mkdir(exist_ok=True)
    cfg,ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    cfg.update(motion_file=str(ROOT/'prepared/motions.yaml'),omni_manifest=str(ROOT/'prepared/manifest.json'))
    # Mass variants use an isolated internally consistent asset, not gravity-only hacks.
    assets=OUT/'assets' if args.mass==1 else OUT/('assets_'+tag)
    ec['uefn_asset_directory']=str(assets/'uefn')
    if args.mass!=1:
        import shutil,hashlib,xml.etree.ElementTree as ET
        shutil.copytree(OUT/'assets',assets,dirs_exist_ok=True)
        xml=assets/'uefn/humanoid_uefn.xml';tree=ET.parse(xml);phys=assets/'uefn/physics.json';p=json.loads(phys.read_text())
        for b in tree.findall('.//body'):
            name=b.get('name','')
            if not any(word in name for word in ('thigh','shin','foot')):continue
            inert=b.find('inertial');assert inert is not None
            for k in ('mass','diaginertia'):inert.set(k,' '.join(str(float(v)*args.mass) for v in inert.get(k).split()))
            for k in ('mass','inertia','drag_mass','drag_first','drag_second'):
                p['bodies'][name][k]=(np.asarray(p['bodies'][name][k])*args.mass).tolist()
        tree.write(xml,encoding='utf-8',xml_declaration=True);p['asset_sha256']=hashlib.sha256(xml.read_bytes()).hexdigest();phys.write_text(json.dumps(p))
        # Motion kinematics must use this mass-equivalent, geometry-identical character.
        cfg['char_file']=str(xml)
    factor=wp.array(np.repeat([c['grip'] for c in cases],S).astype(np.float32),device='cuda:0')
    import contact_manifolds_gpu as manifold
    original_prepare=manifold.prepare
    def prepare(p,ncontact,friction,model,data,inverse,error,mass,inertia):
        wp.launch(grip,(N,friction.shape[1]),inputs=[ncontact,p.contact_ids,data.contact.geom,model.geom_bodyid,friction,factor],device='cuda:0')
        return original_prepare(p,ncontact,friction,model,data,inverse,error,mass,inertia)
    manifold.prepare=prepare
    with np.load(OUT/'replay.npz') as z:
        meta=json.loads(str(z['metadata']));rows=meta['replay_rows'][:S];assert len(rows)==S and rows[3]['iteration']==20426
        initial=np.stack([z['pose'+('' if i==0 else '_'+str(i))][0] for i in range(S)])
        original_poses=[z['pose'+('' if i==0 else '_'+str(i))].copy() for i in range(S)]
    bank_indices=torch.tensor([r['initial_pose_bank_index'] for r in rows]*len(cases),device='cuda:0')
    class Matched(DisabledSlowLocoEnv):
        def _reset_ref_motion(self,ids):
            super()._reset_ref_motion(ids)
            if not hasattr(self,'_init_selection'):return
            ix=bank_indices[ids];self._init_selection[ids]=ix
            times=self._init_times[self._motion_ids[ids],self._codes[ids],ix];self._motion_time_offsets[ids]=times
            vals=self._motion_lib.calc_motion_frame(self._motion_ids[ids],times)
            for dest,v in zip((self._ref_root_pos,self._ref_root_rot,self._ref_root_vel,self._ref_root_ang_vel,self._ref_joint_rot,self._ref_dof_vel),vals):dest[ids]=v
            self._ref_dof_pos[ids]=self._motion_lib.joint_rot_to_dof(vals[4])
            pos,rot=self._kin_char_model.forward_kinematics(vals[0],vals[1],vals[4]);self._ref_body_pos[ids]=pos;self._ref_body_rot[ids]=rot
            for dest in (self._ref_root_vel,self._ref_root_ang_vel,self._ref_dof_vel):dest[ids]*=self._rates[ids,None]
    env=Matched(cfg,ec,N,'cuda:0',False);eng=env._engine;c=env._get_char_id()
    assert (env._codes==12).all() and (env._motor_enabled_binary[:,20:]==0).all()
    # Only arm caps change: shoulders, elbows, wrists. Torso/head remain stock.
    scales=torch.tensor(np.repeat([v['arm'] for v in cases],S),device='cuda:0',dtype=torch.float32)
    strength=env._update_head_strength
    def update_strength():strength();env._motor_mask[:,6:20].mul_(scales[:,None])
    env._update_head_strength=update_strength
    agent=OmniPPOAgent(ac,env,'cuda:0')
    with zipfile.ZipFile(OUT/'checkpoint_0020426.zip') as z:(dest/'model.pt').write_bytes(z.read('model.pt'))
    agent.load(str(dest/'model.pt'));agent.eval();agent.set_mode(AgentMode.TEST)
    counter=wp.zeros(1,dtype=int,device='cuda:0');substeps=args.ticks*8+16
    forces=wp.zeros((substeps,N,15,3),device='cuda:0');slip=wp.zeros((substeps,N,2),device='cuda:0')
    torque=wp.zeros((substeps,N,34),device='cuda:0');mu=wp.zeros((substeps,N,2),device='cuda:0')
    advance=eng._solver._mujoco_warp_step;solver=eng._solver;body=wp.array(solver.mj_model.geom_bodyid.astype(np.int32),device='cuda:0')
    def step():
        advance();wp.launch(measure,N,inputs=[eng.transfer_contact.p,counter,solver.mjw_data.contact.geom,solver.mjw_data.contact.frame,body,forces,slip,torque,mu],device='cuda:0');wp.launch(count,1,inputs=[counter],device='cuda:0')
    eng._solver._mujoco_warp_step=step;eng._build_graphs();counter.zero_();forces.zero_();slip.zero_();torque.zero_();mu.zero_()
    obs,info=env.reset();p0=eng.get_body_pos(c).cpu().numpy().copy()
    init_err=float(np.abs(p0[:S]-initial[:,:,:3]).max());assert init_err<1e-4,init_err
    if args.controller=='pull':
        ids=torch.arange(N,device='cuda:0')
        with np.load(OUT/'pull-fixture.npz') as z:
            q0=torch.tensor(z['initial_q'],device='cuda:0').repeat(len(cases),1)
            target=torch.tensor(z['target_q'],device='cuda:0').repeat(len(cases),1)
            phases=torch.tensor(z['phases'],device='cuda:0',dtype=torch.float32).repeat(len(cases))
        env._time_buf.zero_();env._timestep_buf.zero_();env._done_buf.zero_();env._motion_time_offsets.copy_(phases);env._update_ref_motion()
        vals=env._motion_lib.calc_motion_frame(env._motion_ids,phases)
        torch.testing.assert_close(q0,env._motion_lib.joint_rot_to_dof(vals[4]),atol=1e-5,rtol=1e-5)
        eng.set_root_pos(ids,c,vals[0]);eng.set_root_rot(ids,c,vals[1]);eng.set_dof_pos(ids,c,q0)
        eng.set_root_vel(ids,c,0.);eng.set_root_ang_vel(ids,c,0.);eng.set_dof_vel(ids,c,0.)
        eng._sim_state.pre_step_update();eng._sim_state.eval_fk();eng._body_velocity.update(eng._sim_state.raw_state)
        env._pelvis_window.reset(ids,eng.get_body_pos(c)[:,0],env._ref_body_pos[:,0]);env._crawl_previous_xy.copy_(eng.get_body_pos(c)[:,0,:2])
        p0=eng.get_body_pos(c).cpu().numpy().copy()
    masses=eng._sim_model.body_mass.numpy().reshape(N,15)[0]
    hist={k:[] for k in ('pos','rot','done','reward','action')}
    with torch.no_grad():
        for tick in range(args.ticks):
            if args.controller=='policy':action,_=agent._decide_action(obs,info)
            else:
                alpha=min(1.,(tick+1)/30);alpha=alpha*alpha*(3-2*alpha)
                current=env._kin_char_model.dof_to_rot(eng.get_dof_pos(c));desired=env._kin_char_model.dof_to_rot(q0+(target-q0)*alpha)
                action=(env._kin_char_model.compute_dof_vel(current,desired,1.)*25).clamp(env._action_bound_low,env._action_bound_high)
            obs,reward,done,info=env.step(action)
            for key,v in zip(hist,(eng.get_body_pos(c),eng.get_body_rot(c),done,reward,action)):hist[key].append(v.cpu().numpy().copy())
            if tick%30==29:print('TICK',tick+1,flush=True)
    n=int(counter.numpy()[0]);assert n==args.ticks*8
    err=eng.transfer_contact.error.numpy();assert not err.any(),err
    data={k:np.array(v) for k,v in hist.items()};data.update(initial=p0,force=forces.numpy()[:n],slip=slip.numpy()[:n],torque=torque.numpy()[:n],mu=mu.numpy()[:n])
    np.savez_compressed(dest/'trace.npz',**data)
    summaries=[]
    for j,case in enumerate(cases):
        sl=slice(j*S,(j+1)*S);pos=data['pos'][:,sl];f=data['force'][:,sl];t=data['torque'][:,sl];hs=data['slip'][:,sl]
        loaded=f[:,:,[5,8],2]>10;late=slice(30*8,None);active=loaded[late]
        speed=(pos[-1,:,0,0]-pos[29,:,0,0])/((args.ticks-30)/30)
        footforce=f[:,:,9:,2].sum(-1);handforce=f[:,:,[5,8],2].sum(-1)
        first_fail=[int(np.flatnonzero(data['done'][:,sl][:,i]==1)[0]+1) if (data['done'][:,sl][:,i]==1).any() else args.ticks for i in range(S)]
        caps=wp.to_torch(eng._uefn_motors.upper).cpu().numpy().reshape(-1)[:34]
        summaries.append(dict(**case,dead_leg_mass_scale=args.mass,speed_m_s=speed.tolist(),mean_speed=float(speed.mean()),median_speed=float(np.median(speed)),hand_slip_loaded_m_s=float(hs[late][active].mean()) if active.any() else None,
            hand_load_n=float(handforce[late].mean()),leg_load_n=float(footforce[late].mean()),arm_cap_fraction=float((np.abs(t[late,:,6:20])>=.98*caps[None,None,6:20]*case['arm']).mean()),
            passive_torque_max=float(np.abs(t[:,:,20:]).max()),first_failure_tick=first_fail,selected_row3_speed=float(speed[3]),final_pelvis_z=pos[-1,:,0,2].tolist(),pelvis_displacement_m=(pos[-1,:,0,0]-p0[sl,0,0]).tolist()))
    agreement=[float(np.abs(data['pos'][:min(30,len(p)-1),i]-p[1:min(30,len(p)-1)+1,:,:3]).max()) for i,p in enumerate(original_poses)] if args.controller=='policy' else None
    result=dict(checkpoint=20426,controller=args.controller,case_starts='recorded bank indices' if args.controller=='policy' else 'four zero-velocity authored phases; same independent IK endpoints',indices=bank_indices[:S].cpu().tolist(),initial_pose_error_m=init_err,baseline_first30_pose_error_m=agreement,mass_kg=masses.tolist(),cases=summaries,steps=args.ticks,continued_after_fail_for_diagnosis=True,solver_errors=err.tolist())
    (dest/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(summaries),flush=True)

if __name__=='__main__':main()
