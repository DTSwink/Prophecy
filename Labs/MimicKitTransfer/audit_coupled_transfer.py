"""Same synchronized state/command, one 240 Hz step: no accumulated policy drift."""
import os,json,time
import numpy as np
import torch,warp as wp,mujoco,mujoco_warp as mjw
from scipy.spatial.transform import Rotation as R
import probe
from native_probe import Native,names
from coupled_velocity_motors import CoupledVelocityMotors

def main(tick=0):
    env,agent=probe.setup();e=env._engine;s=e._solver;m=s.mj_model;wm=s.mjw_model;d=s.mjw_data
    env._sample_motion_times=lambda n:(torch.zeros(n,dtype=torch.long),torch.zeros(n))
    obs,info=env.reset()
    warmup_motor=None
    if tick:
        warmup_motor=CoupledVelocityMotors(wm,d,m);warmup_motor.install()
        try:
            for _ in range(tick):
                with torch.no_grad():a,_=agent._decide_action(obs,info)
                obs,_,flag,info=env.step(a)
                assert not flag[0]
        finally:warmup_motor.restore()
    with torch.no_grad():action,_=agent._decide_action(obs,info)
    frozen=[];initial=None
    def snapshot(obj):
        for key,value in vars(obj).items():
            if isinstance(value,wp.array):frozen.append((value,wp.clone(value)))
            elif key in ('contact','efc'):snapshot(value)
    original=s._mujoco_warp_step
    def capture():
        nonlocal initial
        if not frozen:
            snapshot(d);initial=probe.physical_state(env)
        original()
    s._mujoco_warp_step=capture
    try:env.step(action)
    finally:s._mujoco_warp_step=original
    motors=CoupledVelocityMotors(wm,d,m)
    flags=wm.opt.disableflags;grav=wm.opt.gravity;reports=[]
    cases=[('free',('CONTACT','LIMIT','GRAVITY','DRAG','MOTORS')),
           ('free_high_iterations',('CONTACT','LIMIT','GRAVITY','DRAG','MOTORS','HIGH_ITERATIONS')),
           ('zero_velocity_free',('CONTACT','LIMIT','GRAVITY','DRAG','ZERO_VELOCITY','MOTORS','HIGH_ITERATIONS')),
           ('zero_velocity_limits',('CONTACT','GRAVITY','DRAG','ZERO_VELOCITY','MOTORS')),
           ('zero_velocity_limits_high_iterations',('CONTACT','GRAVITY','DRAG','ZERO_VELOCITY','MOTORS','HIGH_ITERATIONS')),
           ('motors_only',('CONTACT','LIMIT','GRAVITY','DRAG')),
           ('motors_only_high_iterations',('CONTACT','LIMIT','GRAVITY','DRAG','HIGH_ITERATIONS')),
           ('zero_velocity_motors',('CONTACT','LIMIT','GRAVITY','DRAG','ZERO_VELOCITY')),
           ('zero_velocity_motors_high_iterations',('CONTACT','LIMIT','GRAVITY','DRAG','ZERO_VELOCITY','HIGH_ITERATIONS')),
           ('motors_gravity',('CONTACT','LIMIT','DRAG')),
           ('motors_gravity_limits',('CONTACT','DRAG')),
           ('contacts_no_drag',('DRAG',)),('complete',()),
           ('complete_high_iterations',('HIGH_ITERATIONS',))]
    command=action[0].numpy().clip(-2*np.pi,2*np.pi)
    saved_env={k:v for k,v in os.environ.items() if k.startswith('TRANSFER_')}
    def error(actual,native):
        return dict(position_cm=float(np.linalg.norm(actual[:,:3]-native[:,:3],axis=1).max()*100),
            angle_deg=float(np.rad2deg((R.from_quat(actual[:,3:7])*R.from_quat(native[:,3:7]).inv()).magnitude()).max()),
            velocity=float(np.linalg.norm(actual[:,7:10]-native[:,7:10],axis=1).max()),
            angular_velocity=float(np.linalg.norm(actual[:,10:13]-native[:,10:13],axis=1).max()),
            angular_by_body=dict(zip(names,np.linalg.norm(actual[:,10:13]-native[:,10:13],axis=1).tolist())))
    try:
        for label,disabled in cases:
            for k in list(os.environ):
                if k.startswith('TRANSFER_'):del os.environ[k]
            os.environ['TRANSFER_SUBSTEPS']='1'
            for flag in disabled:
                suffix={'HIGH_ITERATIONS':'HIGH_ITERATIONS','LIMIT':'NO_LIMITS'}.get(flag,'NO_'+flag)
                os.environ['TRANSFER_'+suffix]='1'
            case_initial=initial.copy()
            if 'ZERO_VELOCITY' in disabled:case_initial[:,7:]=0
            native=Native(case_initial)
            try:
                np.testing.assert_allclose(native.initial['bodies'],case_initial,atol=1e-5)
                predicted=np.array(native.request('step '+' '.join(map(str,command)))['bodies'])
            finally:native.close()
            row=dict(case=label,disabled=list(disabled))
            row['initial']=case_initial.tolist();row['native']=predicted.tolist()
            for mode in ('legacy','coupled'):
                for dest,src in frozen:wp.copy(dest,src)
                if 'ZERO_VELOCITY' in disabled:d.qvel.zero_();d.qacc_warmstart.zero_()
                wm.opt.disableflags=flags
                for flag in disabled:
                    if flag in ('CONTACT','LIMIT','GRAVITY','MOTORS'):
                        wm.opt.disableflags|=int(getattr(mujoco.mjtDisableBit,'mjDSBL_'+('ACTUATION' if flag=='MOTORS' else flag)))
                if 'DRAG' in disabled:
                    # Remove body drag, retaining gyro cancellation to match Jolt.
                    rot=R.from_quat(case_initial[:,3:7]).as_matrix();w=case_initial[:,10:13]
                    inertia=e._sim_model.body_inertia.numpy()
                    gyro=np.cross(w,np.einsum('bij,bj->bi',rot@inertia@rot.transpose(0,2,1),w))
                    force=np.concatenate([np.zeros_like(gyro),gyro],axis=1)
                    f=d.xfrc_applied.numpy();f[0,1:]=force;d.xfrc_applied.assign(f)
                if mode=='coupled':motors.install()
                try:
                    mjw.step(wm,d);actual=probe.physical_state(env)
                    row[mode]=error(actual,predicted)
                    row[mode+'_state']=actual.tolist()
                    if mode=='coupled' and 'MOTORS' not in disabled:row['motor_law_error_nm']=float(motors.stats.numpy()[0,0])
                finally:motors.restore()
            reports.append(row);print('TRANSFER '+json.dumps({k:v for k,v in row.items() if k not in ('initial','native','legacy_state','coupled_state')}),flush=True)
        result=dict(physics_dt=float(wm.opt.timestep.numpy()[0]),checkpoint='3913',fixture='active contact fixture',
                    same_state=True,same_command=True,cases=reports)
        result['captured_policy_tick']=tick
        (probe.OUT/f'coupled-transfer-ablation{("-tick"+str(tick)) if tick else ""}.json').write_text(json.dumps(result,indent=2))
    finally:
        motors.restore();wm.opt.disableflags=flags;wm.opt.gravity=grav
        for k in list(os.environ):
            if k.startswith('TRANSFER_'):del os.environ[k]
        os.environ.update(saved_env)

if __name__=='__main__':main()
