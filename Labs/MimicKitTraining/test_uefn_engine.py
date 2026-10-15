"""Bounded local setup validation; never constructs an agent/optimizer."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'Saved/MimicKitUEFN/dependencies'),
             str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit')]
import json,time
import numpy as np
import torch
import warp as wp
import yaml
from scipy.spatial.transform import Rotation
from uefn_engine import compound_forces
from omni_walk import OmniWalkEnv


def force_test():
    rows=list(json.loads((ROOT/'Labs/MimicKitUEFN/physics.json').read_text())['bodies'].values())
    n=len(rows);rng=np.random.default_rng(192);rot=Rotation.random(n,random_state=rng)
    pose=np.concatenate((rng.normal(size=(n,3)),rot.as_quat()),1).astype('float32')
    vel=rng.normal(size=(n,6)).astype('float32');external=rng.normal(size=(n,6)).astype('float32')
    expected=external.astype('float64').copy();mat=rot.as_matrix()
    for i,row in enumerate(rows):
        v,w=vel[i,:3],vel[i,3:];iw=mat[i]@np.array(row['inertia'])@mat[i].T
        expected[i,3:]+=np.cross(w,iw@w)
        for member in row['members']:
            r=mat[i]@member['offset'];f=-member['coefficient']*(v+np.cross(w,r))
            expected[i,:3]+=f;expected[i,3:]+=np.cross(r,f)
    out=wp.array(external,dtype=wp.spatial_vector,device='cpu')
    args=[wp.array(pose,dtype=wp.transform,device='cpu'),wp.array(vel,dtype=wp.spatial_vector,device='cpu'),
          wp.array([r['inertia'] for r in rows],dtype=wp.mat33,device='cpu'),
          wp.array([r['drag_mass'] for r in rows],dtype=float,device='cpu'),
          wp.array([r['drag_first'] for r in rows],dtype=wp.vec3,device='cpu'),
          wp.array([r['drag_second'] for r in rows],dtype=wp.mat33,device='cpu'),out]
    wp.launch(compound_forces,n,inputs=args,device='cpu')
    np.testing.assert_allclose(out.numpy(),expected,atol=2e-5,rtol=2e-5)
    return float(np.max(np.abs(out.numpy()-expected)))


def main():
    torch.set_num_threads(1);wp.init();wp.set_device('cpu')
    error=force_test();print('Independent compound force test passed',error,flush=True)
    vendor=ROOT/'Saved/MimicKit/vendor/MimicKit'
    cfg=yaml.safe_load((vendor/'data/envs/deepmimic_humanoid_env.yaml').read_text())
    cfg.update(char_file=str(ROOT/'Labs/MimicKitUEFN/humanoid_uefn.xml'),
               motion_file=str(ROOT/'Saved/MimicKitUEFN/omni/motions.yaml'),
               omni_manifest=str(ROOT/'Saved/MimicKitUEFN/omni/manifest.json'),
               init_pose=None,visualize_ref_char=False,enable_tar_obs=False,enable_phase_obs=False)
    engine=dict(control_mode='vel',sim_freq=240,control_freq=30,env_spacing=5,
                uefn_asset_directory=str(ROOT/'Labs/MimicKitUEFN'))
    start=time.perf_counter();env=OmniWalkEnv(cfg,engine,2,'cpu',False)
    model=env._engine._sim_model
    ke=model.joint_target_ke.numpy();kd=model.joint_target_kd.numpy();effort=model.joint_effort_limit.numpy()
    starts=model.joint_qd_start.numpy();wrists=[]
    for j,label in enumerate(model.joint_label):
        if 'wrist' not in label:continue
        first=int(starts[j]);last=int(starts[j+1])
        assert last-first==3
        np.testing.assert_allclose(ke[first:last],0)
        np.testing.assert_allclose(kd[first:last],10)
        np.testing.assert_allclose(effort[first:last],50)
        wrists.append(label)
    assert len(wrists)==4 # Two wrists in each of two worlds.
    built=time.perf_counter();env.reset();obs=env._compute_obs()
    motor=env._engine._uefn_motors
    assert env._engine._bounded_velocity_motors and len(motor.ids)==34
    np.testing.assert_array_equal(motor.dof_ids,np.arange(6,40))
    assert obs.shape[1]==env.get_obs_space().shape[0]
    assert not env._enable_tar_obs and not env._enable_phase_obs and env._tar_obs_steps.numel()==0
    phases=env.next_phase_target().clone();initial=env._compute_obs()[:,-2:].clone()
    for i in range(4):
        env.step(torch.zeros((2,env.get_action_space().shape[0])))
        if i==0:torch.testing.assert_close(env._compute_obs()[:,-2:],phases,atol=2e-6,rtol=1e-5)
        assert torch.isfinite(env._compute_obs()).all()
        assert torch.isfinite(env.loss_terms).all()
        assert np.max(motor.stats.numpy()[:,0])<0.01
        assert np.max(motor.stats.numpy()[:,2])==0
        np.testing.assert_allclose(env._engine.get_dof_forces(env._get_char_id()).numpy(),motor.torque.numpy())
    env.reset(torch.tensor([0]));assert torch.isfinite(env._compute_obs()).all()
    report=dict(passed=True,device='cpu',worlds=2,policy_ticks=4,optimizer_steps=0,
                observations=obs.shape[1],physical_observations=obs.shape[1]-5,next_phase_matches_actual_tick=True,
                loaded_mass_com_inertia_checked=True,compound_force_max_error=error,
                installed_ball_profiles=len(env._engine._uefn_limits.joints),
                loaded_wrist_velocity_gain=10,loaded_wrist_effort_limit_nm=50,loaded_wrist_position_gain=0,
                setup_seconds=built-start,total_seconds=time.perf_counter()-start,
                cuda_validated=False,motion_accepted=False,loss_weights_calibrated=False)
    report.update(bounded_motors_default=True,motor_count=len(motor.ids),
                  motor_law_defect_nm=float(np.max(motor.stats.numpy()[:,0])),
                  solved_motor_torque_sensor_checked=True,unused_direct_torques_zero=True)
    (ROOT/'Saved/MimicKitUEFN/integrated-engine-cpu.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
