"""Paired one-substep predictions from identical states. No policy feedback drift."""
import os,types,json,time
from pathlib import Path
os.environ['MIMICKIT_TRANSFER_OUT']=str(Path(__file__).resolve().parents[2]/'Saved/MimicKitTransfer/no-armature-3913')
os.environ.setdefault('MIMICKIT_TRANSFER_FIXTURE',str(Path(os.environ['MIMICKIT_TRANSFER_OUT'])/'ablation-fixture.exe'))
os.environ['TRANSFER_SUBSTEPS']='1'
import probe
from native_probe import Native,names,np,R
import torch,warp as wp,mujoco
from engines.newton_engine import NewtonEngine

def main():
    env,agent=probe.setup();e=env._engine;wm=e._solver.mjw_model
    original=e._pre_sim_step;old_flags=wm.opt.disableflags;old_gravity=wm.opt.gravity
    inertia=e._sim_model.body_inertia.numpy()
    reports=[];start=time.perf_counter()
    cases=[('baseline',()),('no_contact',('CONTACT',)),('no_contact_limits',('CONTACT','LIMIT')),
           ('no_contact_limits_motors',('CONTACT','LIMIT','ACTUATION')),
           ('no_contact_limits_motors_drag',('CONTACT','LIMIT','ACTUATION','DRAG')),
           ('no_contact_limits_high_iterations',('CONTACT','LIMIT','HIGH_ITERATIONS'))]
    if os.getenv('TRANSFER_SATURATION_AUDIT'):cases=cases[:3]
    if os.getenv('TRANSFER_CONTACT_AUDIT'):cases=cases[:1]
    switches=dict(CONTACT='NO_CONTACT',LIMIT='NO_LIMITS',ACTUATION='NO_MOTORS',DRAG='NO_DRAG',HIGH_ITERATIONS='HIGH_ITERATIONS')
    for label,disabled in cases:
        wm.opt.disableflags=old_flags;wm.opt.gravity=old_gravity;e._pre_sim_step=original
        for s in switches.values():os.environ.pop('TRANSFER_'+s,None)
        env._sample_motion_times=lambda n:(torch.zeros(n,dtype=torch.long),torch.zeros(n))
        obs,info=env.reset()
        with torch.no_grad():action,_=agent._decide_action(obs,info)
        obs,_,_,info=env.step(action) # Same established physical state for every case.
        initial=probe.physical_state(env)
        with torch.no_grad():action,_=agent._decide_action(obs,info)
        commands=action[0].numpy().clip(-2*np.pi,2*np.pi)
        for flag in disabled:
            os.environ['TRANSFER_'+switches[flag]]='1'
            if flag in ('CONTACT','LIMIT','ACTUATION'):
                wm.opt.disableflags |= int(getattr(mujoco.mjtDisableBit,'mjDSBL_'+flag))
        samples=[];pending=None;pending_info=None;input_history=[];output_history=[]
        def compare(actual):
            nonlocal pending
            if pending is None:return
            output_history.append(dict(actual=actual.tolist(),native=pending.tolist(),native_info=pending_info,
                actuator_force=e._solver.mjw_data.actuator_force.numpy().tolist(),
                contacts={field:getattr(e._solver.mjw_data.contact,field).numpy().tolist() for field in ('dist','geom') if hasattr(e._solver.mjw_data.contact,field)},
                contact_counts={field:getattr(e._solver.mjw_data,field).numpy().tolist() for field in ('ncon','nacon') if hasattr(e._solver.mjw_data,field)}))
            if not samples:
                (probe.OUT/f'{label}-motor-output.json').write_text(json.dumps(dict(
                    actual=actual.tolist(),native=pending.tolist(),
                    actuator_force=e._solver.mjw_data.actuator_force.numpy().tolist(),
                    actuator_gain=e._solver.mjw_model.actuator_gainprm.numpy().tolist(),
                    actuator_bias=e._solver.mjw_model.actuator_biasprm.numpy().tolist(),
                    actuator_gear=e._solver.mj_model.actuator_gear.tolist(),
                    actuator_trnid=e._solver.mj_model.actuator_trnid.tolist(),
                    actuator_names=[e._solver.mj_model.actuator(i).name for i in range(e._solver.mj_model.nu)]),indent=2))
            p=np.linalg.norm(pending[:,:3]-actual[:,:3],axis=1)
            a=(R.from_quat(pending[:,3:7])*R.from_quat(actual[:,3:7]).inv()).magnitude()
            v=np.linalg.norm(pending[:,7:10]-actual[:,7:10],axis=1)
            w=np.linalg.norm(pending[:,10:13]-actual[:,10:13],axis=1)
            samples.append(dict(position_cm=float(p.max()*100),angle_deg=float(np.rad2deg(a.max())),
                linear_velocity=float(v.max()),angular_velocity=float(w.max()),worst_angular_body=names[int(w.argmax())],
                by_body_angular_velocity=w.tolist()))
        def before(self,raw,control):
            nonlocal pending,pending_info
            actual=probe.physical_state(env);compare(actual)
            input_history.append(actual.tolist())
            if len(samples)==0:
                debug=dict(commands=commands.tolist(),initial=actual.tolist(),qvel=e._solver.mjw_data.qvel.numpy().tolist(),
                    control_targets=control.joint_target_vel.numpy().tolist(),joint_names=[e._solver.mj_model.joint(i).name for i in range(e._solver.mj_model.njnt)])
                (probe.OUT/f'{label}-motor-inputs.json').write_text(json.dumps(debug,indent=2))
            np.testing.assert_allclose(raw.body_q.numpy()[:,:3],actual[:,:3],atol=1e-5)
            n=Native(actual)
            try:
                result=n.request('step '+' '.join(map(str,commands)))
                pending=np.array(result.pop('bodies'));pending_info=result
            finally:n.close()
            if 'DRAG' in disabled:
                NewtonEngine._pre_sim_step(self,raw,control)
                rot=R.from_quat(actual[:,3:7]).as_matrix();w=actual[:,10:13]
                torque=np.cross(w,np.einsum('bij,bj->bi',rot@inertia@rot.transpose(0,2,1),w))
                raw.body_f.assign(np.concatenate([np.zeros_like(torque),torque],axis=1).astype('float32'))
            else:original(raw,control)
        e._pre_sim_step=types.MethodType(before,e)
        env.step(action);compare(probe.physical_state(env));assert len(samples)==8
        row=dict(case=label,first_substep=samples[0],max_substep_position_cm=max(s['position_cm'] for s in samples),
                 max_substep_angular_velocity=max(s['angular_velocity'] for s in samples),samples=samples)
        reports.append(row);print(json.dumps({k:v for k,v in row.items() if k!='samples'}),flush=True)
        if os.getenv('TRANSFER_CONTACT_AUDIT'):
            (probe.OUT/'contact-substeps.json').write_text(json.dumps(dict(inputs=input_history,outputs=output_history),indent=2))
    filename='first-step-saturation-ablation.json' if os.getenv('TRANSFER_SATURATION_AUDIT') else 'first-step-ablation.json'
    if os.getenv('TRANSFER_CONTACT_AUDIT'):filename='contact-step-ablation.json'
    (probe.OUT/filename).write_text(json.dumps(dict(seconds=time.perf_counter()-start,cases=reports),indent=2))

if __name__=='__main__':main()
