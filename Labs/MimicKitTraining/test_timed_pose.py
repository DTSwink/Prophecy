"""Reward arithmetic, tail boundaries, reset isolation, and real physical rollout."""
import json
import os
import train
import torch
import yaml
from timed_pose import TimedNeutralPoseEnv
from observe import TrainingRecorder

torch.set_num_threads(1)
os.chdir(train.REPO)
cfg = yaml.safe_load((train.ROOT/'pipeline/neutral_pose_env.yaml').read_text())
cfg.update(episode_length=50/30, best_reward=True, tail_velocity_weight=0.02, tail_multiplier=3.0, include_pelvis_velocity=True)
engine = yaml.safe_load((train.REPO/'data/engines/newton_engine.yaml').read_text())
env = TimedNeutralPoseEnv(cfg, engine, 64, 'cuda:0', False)
obs, _ = env.reset()
assert obs.shape == (64,141)
assert env._episode_steps == 50

# Identical improvement gets exactly 4x the reward at tick 0 versus tick 45.
env._initial_mse.fill_(.4); env._best_mse.fill_(.1)
env._best_tick.fill_(45); env._best_tick[0] = 0
env._timestep_buf.fill_(45); env._current_mse = env._pose_mse()
env._update_reward()
torch.testing.assert_close(env._reward_buf[0], 4*env._reward_buf[1])
assert torch.all(env.loss_terms[:,1:] == 0)

# Tail is pure current pose error plus squared actual joint velocities, averaged
# over five frames, with no best-pose reward or root-velocity penalty mixed in.
env._timestep_buf.fill_(46); env._update_reward()
torch.testing.assert_close(env.loss_terms[:,1], 3*env._current_mse/5)
torch.testing.assert_close(env.loss_terms[:,2], 0.06*(env._engine.get_dof_vel(env._get_char_id()).square().mean(-1)+env._engine.get_body_vel(env._get_char_id())[:,0].square().mean(-1)+env._engine.get_body_ang_vel(env._get_char_id())[:,0].square().mean(-1))/5)
assert not env.loss_terms[:,0].any()
env._best_mse[1] = .01; env._best_tick[1] = 12
env.reset(torch.tensor([0],device='cuda:0'))
assert abs(float(env._best_mse[1])-.01)<1e-6 and env._best_tick[1]==12
assert env._best_tick[0]==0 and not env._episode_losses[0].any()
env.take_completed_losses()

directory=train.ROOT/'timed_tail_smoke'
directory.mkdir(exist_ok=True)
recorder=TrainingRecorder(env,directory,lambda:0)
obs,_=env.reset()
initial=env._pose_mse().clone();best=initial.clone();best_tick=torch.zeros_like(best)
expected=torch.zeros((64,3),device='cuda:0');rewards=torch.zeros_like(best)
for t in range(1,51):
    obs,reward,done,_=env.step(env._init_dof_pos.expand(64,-1))
    mse=env._pose_mse()
    if t<=45:
        improved=mse<best
        best_tick=torch.where(improved,t,best_tick)
        best=torch.minimum(best,mse)
    if t==45: expected[:,0]=-(initial-best)*(4-3*best_tick/45)
    if t>45:
        expected[:,1]+=3*mse/5
        expected[:,2]+=0.06*(env._engine.get_dof_vel(env._get_char_id()).square().mean(-1)+env._engine.get_body_vel(env._get_char_id())[:,0].square().mean(-1)+env._engine.get_body_ang_vel(env._get_char_id())[:,0].square().mean(-1))/5
    if t<45: assert not reward.any()
    rewards+=reward
    assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
    assert (done==(2 if t==50 else 0)).all()
    torch.testing.assert_close(obs[:,-1],torch.full((64,),max(0.,1-t/45),device='cuda:0',dtype=torch.float32),atol=1e-6,rtol=0)
torch.testing.assert_close(rewards,-expected.sum(-1))
torch.testing.assert_close(env._episode_losses,expected)
losses=env.take_completed_losses()
for i,k in enumerate(('early_pose','tail_mse','joint_velocity')):
    assert abs(losses[k]-float(expected[:,i].mean()))<1e-4
assert env.take_completed_losses() is None
assert recorder.ready
meta=recorder.finish(0,64*50)
assert abs(meta['rollout_losses']['total']+float(rewards[0]))<1e-4
assert abs(meta['duration_seconds']-50/30)<1e-5
report=dict(passed=True,worlds=64,steps=50,inputs=141,bonus_ratio=4,
            unchanged_time_input=True,partial_reset_isolated=True,
            tail_only_velocity=True,velocity_weight=0.02,tail_multiplier=3,pelvis_velocity=True,losses=losses,finite_physics=True,
            replay_frames=51,no_test_rollouts_in_training=True)
(train.ROOT/'timed_tail_smoke.json').write_text(json.dumps(report,indent=2))
print('TIMED_TAIL_TEST_PASS',json.dumps(report),flush=True)
