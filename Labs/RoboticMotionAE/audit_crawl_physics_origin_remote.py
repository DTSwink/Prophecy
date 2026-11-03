"""Bounded, scratch-only paired physics test; no training/source changes."""
import os,sys,json,time,zipfile,hashlib
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
R=Path('/workspace/mimickit_trial'); OUT=R/'physics-origin-20261103'
sys.path[:0]=[str(OUT/'pipeline'),str(R/'MimicKit/mimickit'),str(OUT/'assets/MimicKitTransfer')]
import numpy as np,torch,warp as wp,yaml,inspect,argparse
from crawl_physics_audit_kernels import sample,inc
from slow_loco_disabled import DisabledSlowLocoEnv
from omni_policy import OmniPPOAgent
from learning.base_agent import AgentMode
from util import mp_util

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--hz',type=int,required=True);args=ap.parse_args();dest=OUT/str(args.hz);dest.mkdir(exist_ok=True)
    torch.set_num_threads(2);torch.set_num_interop_threads(1);torch.manual_seed(20261103)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6798);os.chdir(R/'MimicKit')
    starts=json.loads((OUT/'starts.json').read_text());S=len(starts['indices']);N=S
    bank=torch.tensor(starts['indices'],device='cuda:0')
    cfg,ec,ac=[yaml.safe_load((R/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    cfg.update(motion_file=str(R/'prepared/motions.yaml'),omni_manifest=str(R/'prepared/manifest.json'))
    ec['sim_freq']=args.hz;ec['uefn_asset_directory']=str(OUT/'assets/uefn')
    class Matched(DisabledSlowLocoEnv):
        def _reset_ref_motion(self,ids):
            super()._reset_ref_motion(ids)
            if not hasattr(self,'_init_selection'):return
            ix=bank[ids];self._init_selection[ids]=ix
            times=self._init_times[self._motion_ids[ids],self._codes[ids],ix];self._motion_time_offsets[ids]=times
            vals=self._motion_lib.calc_motion_frame(self._motion_ids[ids],times)
            for dest,v in zip((self._ref_root_pos,self._ref_root_rot,self._ref_root_vel,self._ref_root_ang_vel,self._ref_joint_rot,self._ref_dof_vel),vals):dest[ids]=v
            self._ref_dof_pos[ids]=self._motion_lib.joint_rot_to_dof(vals[4])
            pos,rot=self._kin_char_model.forward_kinematics(vals[0],vals[1],vals[4]);self._ref_body_pos[ids]=pos;self._ref_body_rot[ids]=rot
            for dest in (self._ref_root_vel,self._ref_root_ang_vel,self._ref_dof_vel):dest[ids]*=self._rates[ids,None]
    env=Matched(cfg,ec,N,'cuda:0',False);eng=env._engine;c=env._get_char_id();dt=eng.get_timestep()
    assert (env._codes==12).all()
    names=env._kin_char_model.get_body_names();joints=[]
    for side in ('right','left'):
        for part in ('upper_arm','lower_arm','hand'):
            j=env._kin_char_model.get_joint(names.index(side+'_'+part))
            joints.extend(range(j.dof_idx,j.dof_idx+j.get_dof_dim()))
    assert joints==list(range(6,20))
    # Exactly the same previously recorded commands at all physics timesteps.
    source=np.load(OUT/'commands.npz');commands=source['requested'][:,:S]
    counter=wp.zeros(1,dtype=int,device='cuda:0');maxsteps=300*(args.hz//30)+64
    diag=wp.zeros((maxsteps,N,26),device='cuda:0')
    solver=eng._solver;data=solver.mjw_data;raw=inspect.getclosurevars(solver._mujoco_warp_step).nonlocals['advance']
    start=wp.empty_like(data.qpos);before=wp.empty_like(data.qpos)
    bodies=wp.array(solver.mj_model.geom_bodyid.astype(np.int32),device='cuda:0')
    def step():
        wp.copy(start,data.qpos);raw();wp.copy(before,data.qpos)
        eng.transfer_floor_guard.save_before();eng.transfer_projection.apply(eng.transfer_contact.p.inv,shared=True);eng.transfer_floor_guard.apply()
        wp.launch(sample,N,inputs=[eng.transfer_contact.p,counter,data.contact.geom,bodies,data.contact.frame,data.contact.dist,data.qM,start,before,data.qpos,diag],device='cuda:0')
        wp.launch(inc,1,inputs=[counter],device='cuda:0')
    solver._mujoco_warp_step=step;eng._build_graphs()
    obs,info=env.reset();counter.zero_();diag.zero_()
    p0=eng.get_body_pos(c).cpu().numpy().copy();expected=np.array(starts['initial_view_positions']);expected=expected[:,:,[0,2,1]];expected[:,:,1]*=-1
    assert np.max(np.abs(p0-expected))<1e-4
    history={k:[] for k in ('pos','rot','done','qpos','qvel')}
    t0=time.time()
    with torch.no_grad():
      for tick in range(300):
        obs,reward,done,info=env.step(torch.tensor(commands[tick],device='cuda:0'))
        assert torch.isfinite(obs).all()
        for k,v in zip(history,(eng.get_body_pos(c),eng.get_body_rot(c),done,wp.to_torch(data.qpos),wp.to_torch(data.qvel))):history[k].append(v.cpu().numpy().copy())
        if tick%50==49:print('HZ',args.hz,'TICK',tick+1,flush=True)
    n=int(counter.numpy()[0]);assert n==args.hz*10,(n,args.hz*10)
    errors=eng.transfer_contact.error.numpy();assert not errors.any(),errors
    np.savez_compressed(dest/'trace.npz',initial=p0,substeps=diag.numpy()[:n],**{k:np.array(v) for k,v in history.items()})
    report=dict(completed=True,sim_hz=args.hz,control_hz=30,ticks=300,worlds=N,elapsed_seconds=time.time()-t0,initial_position_error=float(np.abs(p0-expected).max()),solver_errors=errors.tolist(),
        fixed_commands=True,training_changes=False,diagnostic_continues_after_first_failure=True)
    (dest/'result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':main()
