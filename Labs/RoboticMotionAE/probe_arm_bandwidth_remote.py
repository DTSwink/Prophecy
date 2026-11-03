"""Bounded, scratch-only paired physics test; no training/source changes."""
import os,sys,json,time,zipfile,hashlib
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
R=Path('/workspace/mimickit_trial'); OUT=R/'arm-bandwidth-20261103'
sys.path[:0]=[str(OUT/'pipeline'),str(R/'MimicKit/mimickit')]
import numpy as np,torch,warp as wp,yaml
from slow_loco_disabled import DisabledSlowLocoEnv
from omni_policy import OmniPPOAgent
from learning.base_agent import AgentMode
from util import mp_util

def main():
    torch.set_num_threads(2);torch.set_num_interop_threads(1);torch.manual_seed(20261103)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6797);os.chdir(R/'MimicKit')
    starts=json.loads((OUT/'starts.json').read_text());S=len(starts['indices']);N=2*S
    bank=torch.tensor(starts['indices']*2,device='cuda:0')
    cfg,ec,ac=[yaml.safe_load((R/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    cfg.update(motion_file=str(R/'prepared/motions.yaml'),omni_manifest=str(R/'prepared/manifest.json'))
    ec['uefn_asset_directory']=str(R/'assets/uefn')
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
    # Sample the actual slowed reference over two cycles, including its seam.
    length=float(env._motion_lib.get_motion_length(0));ts=torch.arange(0,4*length,dt,device='cuda:0')*.5
    ref=env._motion_lib.calc_motion_frame(torch.zeros(len(ts),device='cuda:0',dtype=torch.long),ts)[5][:,6:20]*.5
    ref_acc=torch.diff(ref,dim=0).abs()/dt
    cap=(torch.quantile(ref_acc,.995,dim=0)*2).clamp_min(10.)
    tau=.08;alpha=1-np.exp(-dt/tau)
    state=torch.zeros((N,14),device='cuda:0')
    original=env._apply_action
    last_input=torch.zeros((N,34),device='cuda:0');last_output=last_input.clone()
    def apply(action):
        clipped=action.clamp(env._action_bound_low,env._action_bound_high)
        last_input.copy_(clipped)
        target=clipped[:,6:20]
        delta=((target-state)*alpha).clamp(-cap*dt,cap*dt)
        state.add_(delta)
        filtered=clipped.clone();filtered[S:,6:20]=state[S:]
        last_output.copy_(filtered);original(filtered)
    env._apply_action=apply
    agent=OmniPPOAgent(ac,env,'cuda:0')
    cp=OUT/'checkpoint_0022054.zip'
    with zipfile.ZipFile(cp) as z:(OUT/'model.pt').write_bytes(z.read('model.pt'))
    agent.load(str(OUT/'model.pt'));agent.eval();agent.set_mode(AgentMode.TEST)
    obs,info=env.reset();state.copy_(eng.get_dof_vel(c)[:,6:20])
    p0=eng.get_body_pos(c).cpu().numpy().copy();rot0=eng.get_body_rot(c).cpu().numpy().copy()
    expected=np.array(starts['initial_view_positions']);expected=expected[:,:,[0,2,1]];expected[:,:,1]*=-1
    err=float(np.abs(p0[:S]-expected).max());assert err<1e-4,err
    np.testing.assert_array_equal(p0[:S],p0[S:])
    # Separate reference-only command pass, testing retained smooth strokes.
    rs=ref[0].clone();rf=[]
    for v in ref:
        rs=rs+((v-rs)*alpha).clamp(-cap*dt,cap*dt);rf.append(rs.clone())
    rf=torch.stack(rf)
    meta=dict(checkpoint=22054,sha256=hashlib.sha256(cp.read_bytes()).hexdigest(),worlds=N,paired_starts=S,
              indices=starts['indices'],initial_pose_max_error_m=err,control_dt=dt,tau_seconds=tau,
              alpha=alpha,acceleration_limits_rad_s2=cap.cpu().tolist(),reference_acceleration_max=ref_acc.max(0).values.cpu().tolist(),
              reference_velocity_rms=float(ref.square().mean().sqrt()),reference_filtered_rms=float(rf.square().mean().sqrt()),
              reference_command_rms_difference=float((rf-ref).square().mean().sqrt()),
              no_training=True,no_production_mutation=True,termination_unchanged=True,
              continued_after_fail_for_diagnosis=True)
    (OUT/'test-config.json').write_text(json.dumps(meta,indent=2))
    hist={k:[] for k in ('pos','rot','done','reward','requested','applied','joint_velocity','torque')}
    with torch.no_grad():
        for tick in range(300):
            action,_=agent._decide_action(obs,info);obs,reward,done,info=env.step(action)
            assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
            for k,v in zip(hist,(eng.get_body_pos(c),eng.get_body_rot(c),done,reward,last_input,last_output,eng.get_dof_vel(c),eng._dof_forces[0])):
                hist[k].append(v.cpu().numpy().copy())
            if tick%30==29:print('TICK',tick+1,flush=True)
    eng.validate_transfer_solver()
    np.savez_compressed(OUT/'trace.npz',initial=p0,initial_rot=rot0,**{k:np.array(v) for k,v in hist.items()})
    meta['completed']=True;meta['ticks']=300
    (OUT/'test-config.json').write_text(json.dumps(meta,indent=2));print('COMPLETE',flush=True)

if __name__=='__main__':main()
