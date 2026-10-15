"""Isolated checkpoint survival tests. Only velocity-motor gains vary.

The proposed runtime change is constant parameter scaling, with no additional
kernels. Substep copies here are diagnostic instrumentation, not deployment.
"""
import os,json,time,argparse,hashlib,sys
from pathlib import Path
os.environ['MIMICKIT_TRANSFER_OUT']=str(Path(__file__).resolve().parents[2]/'Saved/MimicKitTransfer/no-armature-3913')
import probe
import numpy as np
import torch,warp as wp

def snapshot(obj):
    result=[]
    for key,value in vars(obj).items():
        if isinstance(value,wp.array):result.append((value,value.numpy().copy()))
        elif key in ('contact','efc'):result.extend(snapshot(value))
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--scales',type=float,nargs='+',default=[1,.5,.25,.125])
    p.add_argument('--phases',type=int,default=1);p.add_argument('--ticks',type=int,default=300)
    p.add_argument('--tag',default='motor_gain_screen');p.add_argument('--axis',choices=['all','y'],default='all')
    p.add_argument('--confirm',action='store_true');a=p.parse_args()
    start=time.perf_counter();env,agent=probe.setup();e=env._engine;s=e._solver;m=s.mj_model;wm=s.mjw_model
    out=probe.OUT/a.tag;out.mkdir(exist_ok=True)
    checkpoint_hash=hashlib.sha256((probe.OUT/'checkpoint/model.pt').read_bytes()).hexdigest()
    original_gain=wm.actuator_gainprm.numpy().copy();original_bias=wm.actuator_biasprm.numpy().copy()
    ankle_dofs=np.array([i for i in range(6,m.nv) if any(m.body(m.jnt_bodyid[m.dof_jntid[i]]).name.endswith(x) for x in ('right_foot','left_foot'))])
    assert len(ankle_dofs)==6
    ankle_joints=np.unique(m.dof_jntid[ankle_dofs])
    # Newton imports each three-axis XML joint as one spherical MuJoCo joint.
    ids=np.flatnonzero(np.isin(m.actuator_trnid[:,0],ankle_joints))
    if a.axis=='y':
        assert len(ankle_joints)==2
        ids=ids[abs(m.actuator_gear[ids,1])>0]
        assert len(ids)>0 and np.all(np.count_nonzero(m.actuator_gear[ids],axis=1)==1)
    frozen=snapshot(s.mjw_data);solver_step=s._step
    invariant={k:getattr(wm,k).numpy().copy() for k in ('body_mass','body_inertia','dof_armature','actuator_forcerange','actuator_forcelimited')}
    duration=float(env._motion_lib.get_motion_lengths()[0]);original_step=s._mujoco_warp_step
    reports=[];initial_obs={}
    for scale in a.scales:
        gain=original_gain.copy();bias=original_bias.copy()
        gain[...,ids,:]*=scale;bias[...,ids,:]*=scale
        wm.actuator_gainprm.assign(gain);wm.actuator_biasprm.assign(bias)
        for phase in np.arange(a.phases)/a.phases:
            for array,value in frozen:array.assign(value)
            s._step=solver_step
            env._sample_motion_times=lambda n:(torch.zeros(n,dtype=torch.long),torch.full((n,),float(phase*duration)))
            obs,info=env.reset()
            if phase not in initial_obs:initial_obs[phase]=obs.numpy().copy()
            np.testing.assert_array_equal(obs.numpy(),initial_obs[phase])
            qvel=[];torques=[];policy_ticks=[];tick=0
            def traced_step():
                qvel.append(s.mjw_data.qvel.numpy()[0].copy());policy_ticks.append(tick)
                original_step();torques.append(s.mjw_data.qfrc_actuator.numpy()[0].copy())
            s._mujoco_warp_step=traced_step
            states=[probe.state(env)];actions=[];distances=[];targets=[];flags=[]
            phase_start=time.perf_counter()
            try:
                for tick in range(a.ticks):
                    with torch.no_grad():action,_=agent._decide_action(obs,info)
                    actions.append(action.numpy().copy());obs,_,flag,info=env.step(action)
                    state=probe.state(env);assert np.isfinite(state).all() and torch.isfinite(obs).all()
                    states.append(state);flags.append(int(flag[0]))
                    distances.append(env.target_distances_sq.sqrt().numpy()[0].copy())
                    targets.append(torch.cat([env.reward_target_pos,env.reward_target_rot],-1)[0].numpy().copy())
                    if flag[0]:break
            finally:s._mujoco_warp_step=original_step
            qvel.append(s.mjw_data.qvel.numpy()[0].copy())
            v=np.array(qvel);t=np.array(torques);policy_ticks=np.array(policy_ticks)
            # A large velocity reversal within a held policy command; also count
            # consecutive opposite >=80Nm ankle motor torques within that command.
            flips=(v[:-1]*v[1:]<0)&(np.minimum(abs(v[:-1]),abs(v[1:]))>10)
            torque_flip=(t[:-1]*t[1:]<0)&(np.minimum(abs(t[:-1]),abs(t[1:]))>=80)
            torque_flip&=(policy_ticks[:-1]==policy_ticks[1:])[:,None]
            report=dict(scale=scale,phase=float(phase),ticks=len(actions),seconds_simulated=len(actions)/30,
                completed_horizon=flags[-1]==3,done=flags[-1],max_target_distance_m=float(np.max(distances)),
                final_root_height_m=float(states[-1][0,2]),
                ankle_large_reversals=int(flips[:,ankle_dofs].sum()),
                ankle_opposite_near_cap_torques=int(torque_flip[:,ankle_dofs].sum()),
                max_ankle_step_change_rad_s=float(abs(np.diff(v[:,ankle_dofs],axis=0)).max()),
                per_dof_large_reversals={m.joint(m.dof_jntid[i]).name:int(flips[:,i].sum()) for i in range(6,m.nv) if flips[:,i].any()},
                elapsed_s=time.perf_counter()-phase_start)
            stem=f'gain_{scale:g}_phase_{phase:.3f}'
            np.savez_compressed(out/(stem+'.npz'),states=states,actions=actions,dist=distances,targets=targets,
                qvel=v,torque=t,policy_tick=policy_ticks,done=flags)
            reports.append(report);print('RESULT '+json.dumps(report),flush=True)
            for k,value in invariant.items():np.testing.assert_array_equal(getattr(wm,k).numpy(),value)
            result=dict(checkpoint_sha256=checkpoint_hash,changed='both ankle velocity gains only',axes=a.axis,
                physics_dt=1/240,unchanged_caps_inertia_geometry_limits=True,reports=reports,elapsed_s=time.perf_counter()-start)
            (out/'report.json').write_text(json.dumps(result,indent=2))
    assert hashlib.sha256((probe.OUT/'checkpoint/model.pt').read_bytes()).hexdigest()==checkpoint_hash
    wm.actuator_gainprm.assign(original_gain);wm.actuator_biasprm.assign(original_bias)
    return env,agent,reports,a

if __name__=='__main__':
    env,agent,reports,args=main()
    if args.confirm:
        stable=[r for r in reports if r['ankle_large_reversals']==0 and r['ankle_opposite_near_cap_torques']==0]
        if stable:
            chosen=max(stable,key=lambda r:(r['completed_horizon'],r['scale']))
            print('CONFIRM '+json.dumps(chosen),flush=True)
            # Reuse loaded model/environment; no repeated dependency imports or
            # process startup. main restores original motor gains before return.
            probe.setup=lambda:(env,agent)
            sys.argv=[sys.argv[0],'--scales',str(chosen['scale']),'--phases','4',
                '--ticks',str(args.ticks),'--axis',args.axis,'--tag',args.tag+'_confirmation']
            main()
        else:print('No candidate passed the chatter screen; no stable-setting claim.',flush=True)
