"""Representation contract and bounded real-engine floor-only smoke."""
import os, sys, json
from pathlib import Path
os.environ['PYGLET_HEADLESS'] = 'true'
root = Path('/workspace/mimickit_trial')
if not root.exists():
    root = Path(__file__).resolve().parents[2]/'Saved/MimicKit/vendor'
sys.path.insert(0, str(root/'MimicKit/mimickit'))
import torch
from amp_world_bodies import world_body_observations, WorldBodyStandingAMPEnv
from util import torch_util

torch.set_num_threads(1)
torch.manual_seed(42)
pos = torch.randn(2, 3, 15, 3)
rot = torch_util.exp_map_to_quat(torch.randn(2, 3, 15, 3)*.3)
vel, ang = torch.randn_like(pos), torch.randn_like(pos)
original = world_body_observations(pos, rot, vel, ang)
assert original.shape == (2, 675)
yaw = torch_util.exp_map_to_quat(torch.tensor([0., 0., 1.2])).expand_as(rot)
offset = torch.tensor([20., -13., 0.])
turned = world_body_observations(torch_util.quat_rotate(yaw, pos)+offset,
    torch_util.quat_mul(yaw, rot), torch_util.quat_rotate(yaw, vel), torch_util.quat_rotate(yaw, ang))
torch.testing.assert_close(original, turned, atol=4e-6, rtol=1e-5)
raised = world_body_observations(pos+torch.tensor([0., 0., .2]), rot, vel, ang)
diff = (raised-original).reshape(2, 3, 15, 15)
torch.testing.assert_close(diff[..., 2], torch.full((2, 3, 15), .2), atol=1e-6, rtol=0)
for axis in (0, 1):
    tilt = torch.zeros(3); tilt[axis] = .6
    q = torch_util.exp_map_to_quat(tilt).expand_as(rot)
    tilted = world_body_observations(torch_util.quat_rotate(q, pos), torch_util.quat_mul(q, rot), vel, ang)
    assert not torch.allclose(original, tilted), 'Alignment must preserve tilt'
torch.testing.assert_close(original, world_body_observations(pos, -rot, vel, ang))
assert not torch.allclose(original, world_body_observations(pos, rot, vel+1, ang))
assert not torch.allclose(original, world_body_observations(pos, rot, vel, ang+1))
print('PASS: yaw/XY invariance, absolute height/tilt, all-body velocities, quaternion sign invariance, 675 inputs')

if '--physics' in sys.argv:
    import yaml
    os.chdir(root/'MimicKit')
    cfg = yaml.safe_load(Path('data/envs/amp_humanoid_env.yaml').read_text())
    target = json.loads((root/'pipeline/amp_standing_target.json').read_text())
    cfg.update(episode_length=2., num_disc_obs_steps=3, init_pose=target['pose'],
        motion_file=str(root/'pipeline/amp_standing_target.pkl'), reset_seed=20261014,
        reset_joint_noise_degrees=5., reset_floor_clearance_m=.002, upright_cohort_fraction=0.)
    engine = yaml.safe_load(Path('data/engines/newton_engine.yaml').read_text())
    e = WorldBodyStandingAMPEnv(cfg, engine, 512, 'cuda:0', False)
    obs, info = e.reset(); char = e._get_char_id()
    assert obs.shape == (512, 140) and e._disc_obs_buf.shape == (512, 675)
    assert not e._upright_cohort.any()
    back = int(e._starts_on_back.sum()); assert 180 < back < 330
    for _ in range(3):
        ids = torch.randperm(512, device='cuda:0')[:100]; e.reset(ids)
        assert not e._upright_cohort.any()
        hist = e._world_body_history['pos'].get_all()[ids]
        torch.testing.assert_close(hist[:, 0], hist[:, -1])
        torch.testing.assert_close(hist[:, -1], e._engine.get_body_pos(char)[ids], atol=2e-6, rtol=1e-5)
    demo = e.fetch_disc_obs_demo(10).reshape(10, 3, 15, 15)
    assert demo[..., 9:].abs().max() == 0
    torch.testing.assert_close(demo[:, 0], demo[:, 2])
    # Pose in the demo is exactly the approved target, in the same alignment.
    v = torch.tensor(target['pose'], device='cuda:0')[None]
    pp, rr = e._kin_char_model.forward_kinematics(v[:, :3], torch_util.exp_map_to_quat(v[:, 3:6]), e._kin_char_model.dof_to_rot(v[:, 6:]))
    expected = world_body_observations(pp[:, None].expand(-1, 3, -1, -1), rr[:, None].expand(-1, 3, -1, -1), torch.zeros_like(pp[:, None]).expand(-1, 3, -1, -1), torch.zeros_like(pp[:, None]).expand(-1, 3, -1, -1))
    torch.testing.assert_close(demo.flatten(1), expected.expand(10, -1), atol=2e-6, rtol=1e-5)
    e.reset()
    for tick in range(60):
        obs, reward, done, info = e.step(e._init_dof_pos.expand(512, -1))
        assert torch.isfinite(obs).all() and torch.isfinite(info['disc_obs']).all()
        assert (done == (3 if tick == 59 else 0)).all()
        h = e._world_body_history['vel'].get_all()
        torch.testing.assert_close(h[:, -1], e._engine.get_body_vel(char))
    report = dict(passed=True, worlds=512, upright=0, initial_back=back, initial_front=512-back,
        actor_inputs=140, discriminator_inputs=675, actual_reset_history=True,
        floor_timeout_ticks=60, representation_invariance=True, static_demo_exact=True)
    (root/'amp-world-bodies-smoke.json').write_text(json.dumps(report, indent=2))
    print('PHYSICS_PASS', json.dumps(report))

