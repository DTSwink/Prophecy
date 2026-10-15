"""Independent angle, sign, gate and real-step tests for posture shaping."""
import json
import numpy as np
import torch
from scipy.spatial.transform import Rotation as R
from posture_reward import PostureReward
from pathlib import Path

OUT=Path(__file__).resolve().parents[2]/'Saved/Robotics'


def main():
    torch.set_num_threads(1)
    meta=json.loads((OUT/'uefn.json').read_text());reward=PostureReward(meta,'cpu','joint_scaled')
    ref=np.array(meta['reference_qpos'][7:]).reshape(-1,4)
    rng=np.random.default_rng(246);q=R.random(384*len(ref),random_state=rng).as_quat()[:,[3,0,1,2]].reshape(384,-1,4)
    ref_rotation=R.from_quat(np.tile(ref[:,[1,2,3,0]],(384,1)))
    current_rotation=R.from_quat(q[:,:,[1,2,3,0]].reshape(-1,4))
    errors=(ref_rotation.inv()*current_rotation).as_rotvec().reshape(384,-1,3)
    std=np.array(reward.contract['joint_std_rad']);mask=np.array(reward.contract['active_axes'])
    expected=np.exp(-((errors/std)**2*mask).sum((1,2))/mask.sum())
    assert mask.sum()==54
    actual=reward(torch.tensor(q,dtype=torch.float32),torch.zeros(len(q))).numpy()
    np.testing.assert_allclose(actual,expected,atol=1e-8,rtol=2e-5)
    # Meaningful near-reference cases: broad random rotations mostly score zero.
    angles=rng.normal(0,.08,(96,len(ref),3));dq=R.from_rotvec(angles.reshape(-1,3))
    qr=(R.from_quat(np.tile(ref[:,[1,2,3,0]],(96,1)))*dq).as_quat()[:,[3,0,1,2]].reshape(96,-1,4)
    expected_near=np.exp(-((angles/std)**2*mask).sum((1,2))/mask.sum())
    actual_near=reward(torch.tensor(qr,dtype=torch.float32),torch.zeros(96)).numpy()
    np.testing.assert_allclose(actual_near,expected_near,atol=2e-6,rtol=2e-6)
    torch.testing.assert_close(reward(torch.tensor(-qr,dtype=torch.float32),torch.zeros(96)),torch.from_numpy(actual_near),atol=0,rtol=0)
    reference=reward.reference.expand(4,-1,-1)
    gated=reward(reference,torch.tensor([0.,.0999,.1,4.]))
    torch.testing.assert_close(gated,torch.tensor([1.,1.,0.,0.]),atol=1e-6,rtol=0)
    legacy=PostureReward(meta,'cpu','legacy');qt=torch.tensor(q,dtype=torch.float32)
    old=torch.exp(-4*(1-(qt*legacy.reference).sum(-1).square().clamp(0,1)).mean(-1))
    assert torch.equal(old,legacy(qt,torch.zeros(len(q))))
    failed=np.load(OUT/'raw499-all-bank.npz');joints=torch.tensor(failed['qpos'][-1,:,7:]).reshape(126,-1,4)
    old_failed=legacy(joints,torch.zeros(126)).numpy();new_failed=reward(joints,torch.zeros(126)).numpy()

    # Check the complete reward equation on an actual GPU physics step.
    import warp as wp
    wp.init()
    from recovery_env import RecoveryEnv,inverse_rotate
    env=RecoveryEnv(4,auto_reset=False,integrator='implicitfast',native_motors=True,relative_targets=True,
        action_rate_sum=True,reward_dt_scale=True,raw_action_cost=True,ccd_iterations=100,gyroscopic_forces=False,
        posture_profile='joint_scaled',initial='bank',pose_bank='fallen-varied-01.npz')
    env.qpos.copy_(env.bank[:4]);env.qvel.zero_()
    requests=torch.full((4,54),.25,device=env.device)
    _,actual_reward,_,_=env.step(requests)
    gravity_error=(inverse_rotate(env.qpos[:,3:7],env.gravity)-env.reference_gravity).square().sum(-1)
    joint_q=env.qpos[:,7:].cpu().numpy().reshape(-1,len(ref),4)
    actual_angles=(R.from_quat(np.tile(ref[:,[1,2,3,0]],(4,1))).inv()*R.from_quat(joint_q[:,:,[1,2,3,0]].reshape(-1,4))).as_rotvec().reshape(4,-1,3)
    pose=np.exp(-((actual_angles/std)**2*mask).sum((1,2))/mask.sum())*(gravity_error.cpu().numpy()<.1)
    qpos=env.qpos.cpu().numpy();qvel=env.qvel.cpu().numpy()
    waist=np.expm1(qpos[:,2].clip(0,env.root_height))/np.expm1(env.root_height)
    chest=np.expm1(env.site_positions[:,env.chest_site,2].cpu().numpy().clip(0,env.chest_height))/np.expm1(env.chest_height)
    expected_reward=(2*waist+chest+np.exp(-2*gravity_error.cpu().numpy())+.5*pose-.01*54*.25**2-.0001*np.minimum(qvel[:,6:]**2,400).mean(1))/30
    np.testing.assert_allclose(actual_reward.cpu().numpy(),expected_reward,atol=2e-7,rtol=1e-5)
    report={'passed':True,'rig_sha256':meta['rig_sha256'],'contract':reward.contract,
        'random_quaternion_cases':384,'near_reference_cases':96,'double_cover_invariant':True,
        'legacy_reward_bitwise_preserved':True,'full_gpu_reward_equation_passed':True,
        'near_reference_max_error':float(abs(actual_near-expected_near).max()),
        'failed_floor_posture_fraction_before':np.quantile(old_failed,[0,.5,1]).tolist(),
        'failed_floor_posture_fraction_after':np.quantile(new_failed,[0,.5,1]).tolist()}
    (OUT/'posture-reward-tests.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))


if __name__=='__main__':main()
