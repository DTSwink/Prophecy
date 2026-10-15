"""Independent force equation and actual-rig tests for the native PD trial."""
import json
import argparse
import numpy as np
import torch
import warp as wp
import mujoco
from scipy.spatial.transform import Rotation
from recovery_env import RecoveryEnv,OUT
from test_phat_constraints import reference


def main():
    p=argparse.ArgumentParser();p.add_argument('--relative-targets',action='store_true')
    p.add_argument('--contacts',type=int,default=256);p.add_argument('--constraints',type=int,default=768)
    p.add_argument('--ccd-iterations',type=int,default=50)
    p.add_argument('--no-gyroscopic-forces',action='store_true')
    p.add_argument('--output');args=p.parse_args()
    torch.set_num_threads(1);torch.manual_seed(192);wp.init()
    env=RecoveryEnv(128,integrator='implicitfast',native_motors=True,relative_targets=args.relative_targets,
        contact_capacity=args.contacts,constraint_capacity=args.constraints,ccd_iterations=args.ccd_iterations,gyroscopic_forces=not args.no_gyroscopic_forces)
    env.qpos.copy_(env.reference[None,:]);env.qvel.normal_(0,.4)
    rng=np.random.default_rng(614)
    varied=env.qpos.cpu().numpy().copy()
    for j in env.metadata['joints']:
        qa=int(env.sim.mj_model.joint(j['name']).qposadr[0])
        original=Rotation.from_quat(np.asarray(j['reference_wxyz'])[[1,2,3,0]])
        changed=original*Rotation.from_rotvec(rng.normal(0,.08,(env.num_envs,3)))
        varied[:,qa:qa+4]=changed.as_quat()[:,[3,0,1,2]]
    env.qpos.copy_(torch.tensor(varied,device=env.device))
    env.controller.actions.uniform_(-env.controller.action_bound,env.controller.action_bound)
    wp.capture_launch(env.sim.forward_graph)
    q=env.qpos.cpu().numpy();v=env.qvel.cpu().numpy();actions=env.controller.actions.cpu().numpy()
    actual=env.sim.wp_data.actuator_force.numpy();expected=np.empty_like(actual)
    indices=env.controller.indices.numpy();gains=env.controller.gains.numpy()
    for ji,j in enumerate(env.metadata['joints']):
        qa=int(env.sim.mj_model.joint(j['name']).qposadr[0]);da=int(env.sim.mj_model.joint(j['name']).dofadr[0])
        target=reference(q[:,qa:qa+4]).astype(np.float64) if args.relative_targets else np.tile(reference(np.array(j['reference_wxyz'])),(env.num_envs,1))
        target[:,np.array(j['modes'])==2]=0
        angles=np.array(j['limits_rad']);scale=angles.copy();scale[1:]=np.sin(angles[1:]/2)
        if args.relative_targets:
            kp,_,cap=gains[ji];scale[:]=.25*(cap/np.sqrt(3))/kp;scale[1:]=np.sin(scale[1:]/2)
        for axis,index in enumerate(indices[ji]):
            if index>=0:target[:,axis]+=actions[:,index]*scale[axis]
        target[:,0]=np.clip(target[:,0],-angles[0],angles[0])
        radius=np.sqrt(((target[:,1:]/np.sin(angles[1:]/2))**2).sum(1))
        target[:,1:]/=np.maximum(radius,1)[:,None]
        sw=Rotation.from_quat(np.column_stack([np.zeros(env.num_envs),target[:,1:],np.sqrt(1-(target[:,1:]**2).sum(1))]))
        tw=Rotation.from_rotvec(np.column_stack([target[:,0],np.zeros((env.num_envs,2))]))
        current=Rotation.from_quat(q[:,qa:qa+4][:,[1,2,3,0]])
        error=(current.inv()*sw*tw).as_rotvec();kp,kd,cap=gains[ji]
        expected[:,ji*3:ji*3+3]=np.clip(kp*error-kd*v[:,da:da+3],-cap/np.sqrt(3),cap/np.sqrt(3))
    error=float(np.max(abs(actual-expected)));assert error<1e-4,error
    assert np.max(abs(env.sim.wp_data.qfrc_actuator.numpy()[:,:6]))==0
    gyro_error=0.
    if args.no_gyroscopic_forces:
        model=env.sim.mj_model;cpu=mujoco.MjData(model);forces=env.sim.wp_data.xfrc_applied.numpy()
        for world in range(16):
            cpu.qpos[:]=q[world];cpu.qvel[:]=v[world];mujoco.mj_forward(model,cpu)
            for body in range(1,model.nbody):
                spatial=np.empty(6);mujoco.mj_objectVelocity(model,cpu,mujoco.mjtObj.mjOBJ_BODY,body,spatial,0)
                basis=cpu.ximat[body].reshape(3,3);inertia=basis@np.diag(model.body_inertia[body])@basis.T
                expected_torque=np.cross(spatial[:3],inertia@spatial[:3])
                gyro_error=max(gyro_error,float(np.abs(forces[world,body,3:]-expected_torque).max()))
        assert gyro_error<1e-5,gyro_error
    # Reference settling, gravity off only for this controller diagnostic.
    env.sim.wp_model.opt.gravity.fill_(wp.vec3(0.))
    env.qpos.copy_(env.reference[None,:]);env.qpos[:,2]+=3;env.qvel.zero_()
    env.qvel[:,6:].normal_(0,.2)
    for _ in range(240):env.controller.actions.zero_();wp.capture_launch(env.policy_step_graph)
    settled=float(env.qvel[:,6:].norm(dim=1).max());assert settled<.1,settled
    env.sim.wp_model.opt.gravity.fill_(wp.vec3(0.,0.,-9.81))
    env.reset(torch.ones(env.num_envs,dtype=torch.bool,device='cuda'))
    peak=0.;body_angular_peak=torch.zeros(env.sim.mj_model.nbody,device=env.device)
    body_velocities=wp.to_torch(env.sim.wp_data.cvel)
    for tick in range(400):
        env.step(torch.randn_like(env.controller.actions))
        velocity=float(env.qvel.abs().max());peak=max(peak,velocity)
        body_angular_peak=torch.maximum(body_angular_peak,body_velocities[:,:,:3].norm(dim=-1).amax(dim=0))
        assert torch.isfinite(env.qpos).all() and torch.isfinite(env.qvel).all() and velocity<500,(tick,velocity)
    report={'passed':True,'controller':env.controller.contract,'rig_sha256':env.metadata['rig_sha256'],
        'native_force_equation_max_error_nm':error,'root_actuation':0,'airborne_initial_joint_velocity_std':.2,
        'airborne_settled_joint_speed_norm':settled,
        'random_worlds':env.num_envs,'random_policy_ticks':400,'peak_abs_velocity':peak,
        'capacity_peaks':env.controller.capacity_max.numpy().tolist(),'contact_capacity':args.contacts,'constraint_capacity':args.constraints,
        'ccd_iterations':args.ccd_iterations,'gyroscopic_forces':not args.no_gyroscopic_forces,
        'full_rig_gyro_term_max_error_nm':gyro_error}
    report['force_equation_pose_perturbation_std_rad']=.08
    report['sampled_body_angular_peak_rad_s']={env.sim.mj_model.body(i).name:float(v) for i,v in enumerate(body_angular_peak.cpu()) if i}
    (OUT/(args.output or ('relative-native-tests.json' if args.relative_targets else 'native-motor-tests.json'))).write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
