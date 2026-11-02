"""Isolated planted-palm pull: actual physics, zero leg torque, no learned policy."""
from probe import *
from scipy.spatial.transform import Rotation as R
OUT=ROOT/'crawl-capacity-20261102/selective'
OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'assets/MimicKitTransfer'))
from sequential_contact_gpu import ContactProblem

@wp.kernel
def record(p:ContactProblem, counter:wp.array(dtype=int), geom:wp.array(dtype=wp.vec2i),
           frames:wp.array(dtype=wp.mat33), bodies:wp.array(dtype=int),
           force:wp.array4d(dtype=float), torque:wp.array3d(dtype=float), velocity:wp.array3d(dtype=float)):
    w=wp.tid();s=counter[0]
    for j in range(p.nmotor):
        torque[s,w,j]=p.motor_impulse[w,j]/p.dt[0]
        velocity[s,w,j]=p.velocity[w,p.dofs[j]]
    for c in range(p.ncontact[w]):
        ident=p.manifold.contact_ids[w,c];pair=geom[ident]
        if bodies[pair[0]]!=0 and bodies[pair[1]]!=0:continue
        f=frames[ident][0]*p.contact_impulse[w,c,0]/p.dt[0]
        g=p.manifold.group[w,c]
        if g>=0:
            f+=(p.manifold.frame[w,g][1]*p.contact_impulse[w,c,1]+p.manifold.frame[w,g][2]*p.contact_impulse[w,c,2])/p.dt[0]
        for side in range(2):
            body=bodies[pair[side]]
            if body>0:
                for k in range(3):force[s,w,body-1,k]+=float(2*side-1)*f[k]

@wp.kernel
def count(counter:wp.array(dtype=int)):
    counter[0]+=1

def main():
    torch.set_num_threads(2);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0')
    mp_util.init(0,1,'cuda:0',6788);os.chdir(ROOT/'MimicKit')
    cfg,ec=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine')]
    cfg.update(capacity_probe_all_crawl=True,motion_file=str(ROOT/'prepared/motions.yaml'),omni_manifest=str(ROOT/'prepared/manifest.json'))
    cases=[]
    groups={'shoulders':[6,7,8,13,14,15],'elbows':[9,16],'wrists':[10,11,12,17,18,19],'torso':[0,1,2]}
    choices=[('baseline',1),('shoulders',2),('shoulders',4),('elbows',2),('elbows',4),('wrists',2),('wrists',4),('torso',2),('torso',4),('shoulders_elbows',2),('full',2),('full',4),('hold',1),('off',0),('baseline20cm',1),('shoulders20cm',2)]
    for group,mult in choices:
        weight=np.ones(20)
        if group in ('full','off'):weight[:]=mult
        elif group=='shoulders_elbows':weight[groups['shoulders']+groups['elbows']]=mult
        elif group=='shoulders20cm':weight[groups['shoulders']]=mult
        elif group in groups:weight[groups[group]]=mult
        cases.append(dict(dx=0. if group in ('hold','off') else .2 if '20cm' in group else .35,duration=1.,scale=1.,kind=group,joint_scale=weight.tolist()))
    S=4;N=len(cases)*S;env=DisabledSlowLocoEnv(cfg,ec,N,'cuda:0',False);eng=env._engine;c=env._get_char_id()
    ids=torch.arange(N,device='cuda:0');env.reset();env._time_buf.zero_();env._timestep_buf.zero_();env._done_buf.zero_()
    phases=torch.tensor([0,1,3,4],device='cuda:0')/8*env._motion_lib.get_motion_length(0)
    env._motion_time_offsets.copy_(phases.repeat(len(cases)));env._update_ref_motion()
    vals=env._motion_lib.calc_motion_frame(env._motion_ids,env._motion_time_offsets);q0=env._motion_lib.joint_rot_to_dof(vals[4]);cpu=eng._solver.mj_model
    data=mujoco.MjData(cpu);qtargets=[];diagnostics=[]
    for row in range(N):
        data.qpos[:3]=vals[0][row].cpu();data.qpos[3:7]=vals[1][row].cpu().numpy()[[3,0,1,2]]
        for b in range(1,15):
            j=env._kin_char_model.get_joint(b);a=cpu.jnt_qposadr[b];v=q0[row,j.dof_idx:j.dof_idx+j.get_dof_dim()].cpu().numpy()
            if len(v)==3:data.qpos[a:a+4]=R.from_rotvec(v).as_quat()[[3,0,1,2]]
            else:data.qpos[a]=v[0]
        data.qvel[:]=0;mujoco.mj_forward(cpu,data)
        targets=[(data.xpos[b].copy(),data.xmat[b].reshape(3,3).copy()) for b in (6,9)]
        data.qpos[0]+=cases[row//S]['dx']
        for it in range(70):
            mujoco.mj_forward(cpu,data);v=np.zeros(cpu.nv)
            for b,di,(pos,rot) in zip((6,9),(np.arange(12,19),np.arange(19,26)),targets):
                jp=np.zeros((3,cpu.nv));jr=np.zeros_like(jp);mujoco.mj_jacBody(cpu,data,jp,jr,b)
                err=np.r_[pos-data.xpos[b],.2*R.from_matrix(rot@data.xmat[b].reshape(3,3).T).as_rotvec()]
                J=np.r_[jp[:,di],.2*jr[:,di]];step=J.T@np.linalg.solve(J@J.T+np.eye(6)*1e-5,err)
                v[di]=step/max(1.,np.linalg.norm(step)/.12)
            mujoco.mj_integratePos(cpu,data.qpos,v,1.)
        mujoco.mj_forward(cpu,data);qt=q0[row].cpu().numpy().copy()
        for b in range(3,9):
            j=env._kin_char_model.get_joint(b);a=cpu.jnt_qposadr[b]
            qt[j.dof_idx:j.dof_idx+j.get_dof_dim()]=R.from_quat(data.qpos[a:a+4][[1,2,3,0]]).as_rotvec() if j.get_dof_dim()==3 else data.qpos[a]
        qtargets.append(qt);diagnostics.append([float(np.linalg.norm(pos-data.xpos[b])) for b,(pos,rot) in zip((6,9),targets)])
    target=torch.tensor(np.array(qtargets),device='cuda:0',dtype=torch.float32)
    eng.set_root_pos(ids,c,vals[0]);eng.set_root_rot(ids,c,vals[1]);eng.set_dof_pos(ids,c,q0)
    eng.set_root_vel(ids,c,0.);eng.set_root_ang_vel(ids,c,0.);eng.set_dof_vel(ids,c,0.)
    eng._sim_state.pre_step_update();eng._sim_state.eval_fk();eng._body_velocity.update(eng._sim_state.raw_state)
    env._motor_enabled_binary[:,:20]=1;env._motor_enabled_binary[:,20:]=0;env._motor_enabled_binary[-S:,20:]=0
    scales=torch.tensor([x['joint_scale'] for x in cases for _ in range(S)],device='cuda:0')
    env._update_head_strength();env._motor_mask[:,:20].mul_(scales)
    # Actual per-substep contact impulses include manifold tangential friction;
    # the engine's stock ground sensor reports normal force only in this solver.
    STEPS=75;substeps=STEPS*8+16;counter=wp.zeros(1,dtype=int,device='cuda:0')
    forces=wp.zeros((substeps,N,15,3),device='cuda:0');torques=wp.zeros((substeps,N,34),device='cuda:0');velocities=wp.zeros((substeps,N,34),device='cuda:0')
    advance=eng._solver._mujoco_warp_step;solver=eng._solver;body=wp.array(cpu.geom_bodyid.astype(np.int32),device='cuda:0')
    def step():
        advance();wp.launch(record,N,inputs=[eng.transfer_contact.p,counter,solver.mjw_data.contact.geom,solver.mjw_data.contact.frame,body,forces,torques,velocities],device='cuda:0')
        wp.launch(count,1,inputs=[counter],device='cuda:0')
    eng._solver._mujoco_warp_step=step
    eng._build_graphs()
    counter.zero_();forces.zero_();torques.zero_();velocities.zero_()
    duration=torch.tensor([x['duration'] for x in cases for _ in range(S)],device='cuda:0')[:,None]
    initial=eng.get_body_pos(c).cpu().numpy().copy();hist=[];rots=[];commands=[]
    for tick in range(STEPS):
        alpha=(((tick+1)/30)/duration).clamp(0,1);alpha=alpha*alpha*(3-2*alpha)
        # Short joint-space interpolation of IK endpoints; physical motor caps,
        # collisions and joint limits remain the actual deployed implementation.
        desired=q0+(target-q0)*alpha
        cur=env._kin_char_model.dof_to_rot(eng.get_dof_pos(c));want=env._kin_char_model.dof_to_rot(desired)
        action=env._kin_char_model.compute_dof_vel(cur,want,1.)*25
        action=action.clamp(env._action_bound_low,env._action_bound_high)
        eng.set_cmd(c,action);eng.step();hist.append(eng.get_body_pos(c).cpu().numpy().copy());rots.append(eng.get_body_rot(c).cpu().numpy().copy());commands.append(action.cpu().numpy().copy())
        if tick%15==14:print('PULL TICK',tick+1,flush=True)
    n=int(counter.numpy()[0]);assert n==STEPS*8,(n,STEPS*8)
    err=eng.transfer_contact.error.numpy();assert not err.any(),err
    np.savez_compressed(OUT/'pull.npz',pos=np.array(hist),rot=np.array(rots),initial_pos=initial,initial_q=q0.cpu().numpy(),target_q=target.cpu().numpy(),command=np.array(commands),force=forces.numpy()[:n],torque=torques.numpy()[:n],qvel=velocities.numpy()[:n])
    (OUT/'pull-metadata.json').write_text(json.dumps(dict(cases=cases,seeds=S,phases=phases.cpu().tolist(),ik_errors_m=diagnostics,solver_error=err.tolist(),substeps=n,dt=1/240,method=__doc__),indent=2))
    print('COMPLETE PULL',flush=True)

if __name__=='__main__':main()
