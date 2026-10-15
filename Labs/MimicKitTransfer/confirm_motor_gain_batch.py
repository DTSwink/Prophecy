"""Four independent gait starts in one CPU batch; unchanged checkpoint.

Batching amortizes Python/Warp launch overhead during local diagnostics.
No source assets, installed libraries, gameplay or checkpoints are edited.
"""
import os,json,time,hashlib,argparse
from pathlib import Path
os.environ['MIMICKIT_TRANSFER_OUT']=str(Path(__file__).resolve().parents[2]/'Saved/MimicKitTransfer/no-armature-3913')
import probe
import numpy as np
import torch,warp as wp,yaml,mujoco

def main():
    p=argparse.ArgumentParser();p.add_argument('--gain',type=float,default=20)
    p.add_argument('--gains',type=float,nargs=3)
    p.add_argument('--output-tag',help='Separate evidence directory; preserve previous captures')
    p.add_argument('--capped',action='store_true',help='Test implicit bounded motors; original gains unchanged')
    p.add_argument('--coupled',action='store_true',help='Solve bounded motors jointly with contacts/limits')
    a=p.parse_args()
    if a.coupled:a.capped=True
    gains=np.array(a.gains or [a.gain]*3)
    if a.capped:gains=np.full(3,40.)
    assert np.all((gains>0)&(gains<=40))
    torch.set_num_threads(1)
    if torch.get_num_interop_threads()!=1:torch.set_num_interop_threads(1)
    wp.init();wp.set_device('cpu')
    if probe.mp_util.global_mp_device is None:probe.mp_util.init(0,1,'cpu',6732)
    else:assert probe.mp_util.global_mp_device=='cpu' and probe.mp_util.global_num_procs==1
    os.chdir(probe.SOURCE/'MimicKit');configs=[]
    for name in ('env','engine','agent'):
        configs.append(yaml.safe_load((probe.OUT/f'checkpoint/{name}_config.yaml').read_text().replace('/workspace/mimickit_trial',probe.SOURCE.as_posix())))
    env=probe.OmniWalkEnv(configs[0],configs[1],4,'cpu',False)
    agent=probe.OmniPPOAgent(configs[2],env,'cpu');agent.load(str(probe.OUT/'checkpoint/model.pt'))
    agent.eval();agent.set_mode(probe.AgentMode.TEST)
    e=env._engine;s=e._solver;m=s.mj_model;wm=s.mjw_model
    dofs=np.array([i for i in range(6,m.nv) if any(m.body(m.jnt_bodyid[m.dof_jntid[i]]).name.endswith(x) for x in ('right_foot','left_foot'))])
    assert len(dofs)==6
    ids=np.flatnonzero(np.isin(m.actuator_trnid[:,0],m.dof_jntid[dofs]))
    invariant={k:getattr(wm,k).numpy().copy() for k in ('body_mass','body_inertia','dof_armature','actuator_forcerange','actuator_forcelimited')}
    if a.capped:
        for k in ('actuator_gainprm','actuator_biasprm'):invariant[k]=getattr(wm,k).numpy().copy()
    gain=wm.actuator_gainprm.numpy().copy();bias=wm.actuator_biasprm.numpy().copy()
    assert np.all(np.count_nonzero(m.actuator_gear[ids],axis=1)==1)
    axes=np.argmax(abs(m.actuator_gear[ids,:3]),axis=1)
    factors=gains[axes]/40
    gain[...,ids,:]*=factors[:,None];bias[...,ids,:]*=factors[:,None]
    wm.actuator_gainprm.assign(gain);wm.actuator_biasprm.assign(bias)
    capped=None;solve_stats=[]
    if a.capped:
        if a.coupled:
            from coupled_velocity_motors import CoupledVelocityMotors as Integrator
        else:
            assert np.all(s.mjw_data.ctrl.numpy()[:,capped.direct_ids]==0), 'Unexpected external torque actuator input'
            from capped_velocity_integrator import CappedVelocityIntegrator as Integrator
        capped=Integrator(wm,s.mjw_data,m);capped.install()
    duration=float(env._motion_lib.get_motion_lengths()[0]);phases=np.arange(4)/4
    env._sample_motion_times=lambda n:(torch.zeros(n,dtype=torch.long),torch.tensor(phases*duration,dtype=torch.float32))
    obs,info=env.reset();original_step=s._mujoco_warp_step
    velocities=[];torques=[];states=[];dist=[];actions=[];targets=[];observations=[obs.numpy().copy()]
    first_physical=[];first_done=np.zeros(4,dtype=int);terminal=np.zeros(4,dtype=int)
    def state():
        c=env._get_char_id()
        return torch.cat([e.get_body_pos(c),e.get_body_rot(c),e.get_body_vel(c),e.get_body_ang_vel(c)],-1).numpy().copy()
    def traced():
        velocities.append(s.mjw_data.qvel.numpy().copy());original_step()
        if capped is None:torques.append(s.mjw_data.qfrc_actuator.numpy().copy())
        else:
            force=np.zeros((4,m.nv));force[:,capped.dof_ids]=capped.torque.numpy()
            torques.append(force);solve_stats.append(capped.stats.numpy().copy())
    s._mujoco_warp_step=traced;states.append(state());start=time.perf_counter()
    try:
        for tick in range(300):
            with torch.no_grad():action,_=agent._decide_action(obs,info)
            actions.append(action.numpy().copy());obs,_,flag,info=env.step(action);observations.append(obs.numpy().copy())
            current=state();assert np.isfinite(current[first_done==0]).all()
            if tick==0:
                qpos=s.mjw_data.qpos.numpy();qvel=s.mjw_data.qvel.numpy()
                for world in range(4):
                    md=mujoco.MjData(m);md.qpos[:]=qpos[world];md.qvel[:]=qvel[world];mujoco.mj_forward(m,md);rows=[]
                    for name in env._kin_char_model.get_body_names():
                        bodies=[b for b in range(1,m.nbody) if m.body(b).name.endswith(name)]
                        assert len(bodies)==1
                        b=bodies[0];jp=np.zeros((3,m.nv));jr=jp.copy();mujoco.mj_jacBodyCom(m,md,jp,jr,b)
                        rows.append(np.r_[md.xpos[b],np.roll(md.xquat[b],-1),jp@md.qvel,jr@md.qvel])
                    first_physical.append(rows)
            states.append(current);dist.append(env.target_distances_sq.sqrt().numpy().copy())
            targets.append(torch.cat([env.reward_target_pos,env.reward_target_rot],-1).numpy().copy())
            ended=(flag.numpy()!=0)&(first_done==0)
            for i in np.flatnonzero(ended):
                first_done[i]=tick+1;terminal[i]=int(flag[i]);print('TERMINAL '+json.dumps(dict(phase=float(phases[i]),tick=tick+1,done=int(flag[i]))),flush=True)
            if tick%30==29:print(f'PROGRESS {tick+1}/300, active {int(np.sum(first_done==0))}',flush=True)
            if np.all(first_done>0):break
    finally:
        s._mujoco_warp_step=original_step
        if capped is not None:capped.restore()
    velocities.append(s.mjw_data.qvel.numpy().copy());v=np.array(velocities);t=np.array(torques)
    label='_'.join(f'{x:g}' for x in gains)
    out=probe.OUT/(a.output_tag or ('coupled_integrator_batch' if a.coupled else 'capped_integrator_batch' if capped is not None else f'motor_gain_{label}_batch'));out.mkdir(exist_ok=True)
    # Preserve expensive physical evidence before formatting any summaries.
    np.savez_compressed(out/'raw.npz',states=states,actions=actions,targets=targets,dist=dist,
        qvel=v,torque=t,obs=observations,first_physical=first_physical,
        solve_stats=solve_stats,first_done=first_done,terminal=terminal)
    reports=[]
    for i,phase in enumerate(phases):
        length=int(first_done[i] or len(actions));vv=v[:length*8+1,i];tt=t[:length*8,i]
        flips=(vv[:-1]*vv[1:]<0)&(np.minimum(abs(vv[:-1]),abs(vv[1:]))>10)
        tf=(tt[:-1]*tt[1:]<0)&(np.minimum(abs(tt[:-1]),abs(tt[1:]))>=80)
        tf&=(np.arange(len(tt)-1)//8==np.arange(1,len(tt))//8)[:,None]
        report=dict(phase=float(phase),ticks=length,completed_horizon=bool(terminal[i]==3),done=int(terminal[i]),
            max_target_distance_m=float(np.max(np.array(dist)[:length,i])),
            ankle_large_reversals=int(flips[:,dofs].sum()),ankle_opposite_near_cap_torques=int(tf[:,dofs].sum()),
            max_ankle_step_change_rad_s=float(abs(np.diff(vv[:,dofs],axis=0)).max()))
        reports.append(report);print('RESULT '+json.dumps(report),flush=True)
    for k,value in invariant.items():np.testing.assert_array_equal(getattr(wm,k).numpy(),value)
    result=dict(gains=gains.tolist(),checkpoint_sha256=hashlib.sha256((probe.OUT/'checkpoint/model.pt').read_bytes()).hexdigest(),
        physics_dt=1/240,changed='implicit bounded motor integration only' if capped else 'both ankle velocity gains only',unchanged_caps_inertia_geometry_limits=True,
        seconds=time.perf_counter()-start,reports=reports)
    if capped is not None:
        result['max_motor_equation_defect_nm']=float(np.array(solve_stats)[:,:,0].max())
        result['max_constraint_rows' if a.coupled else 'max_solver_sweeps']=int(np.array(solve_stats)[:,:,1].max())
    (out/'report.json').write_text(json.dumps(result,indent=2))

if __name__=='__main__':main()
