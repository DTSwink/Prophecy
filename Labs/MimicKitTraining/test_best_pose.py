"""Validate episode minimum accounting, reset isolation and real physics."""
import json
import os
import train
import torch
import yaml
from neutral_pose import NeutralPoseEnv

torch.set_num_threads(1)
os.chdir(train.REPO)
cfg=yaml.safe_load((train.ROOT/'pipeline/neutral_pose_env.yaml').read_text())
cfg['best_reward']=True
engine=yaml.safe_load((train.REPO/'data/engines/newton_engine.yaml').read_text())
env=NeutralPoseEnv(cfg,engine,64,'cuda:0',False)
obs,_=env.reset()
assert obs.shape==(64,141)
assert env.task_name=='best_neutral_pose_mse'
initial=env._pose_mse().clone()
torch.testing.assert_close(env._best_mse,initial)
assert torch.equal(obs[:,-1],torch.ones(64,device="cuda:0"))

# An earlier best pose must survive later deterioration, independently per world.
original=env._pose_mse
fake=initial*2
env._pose_mse=lambda:fake
env._update_misc()
torch.testing.assert_close(env._best_mse,initial)
fake=initial.clone();fake[0]=.07;fake[1]=.08
env._update_misc()
fake=initial*2
env._update_misc()
assert abs(float(env._best_mse[0])-.07)<1e-6
assert abs(float(env._best_mse[1])-.08)<1e-6
env._timestep_buf[:]=44;env._update_reward();assert not env._reward_buf.any()
env._timestep_buf[:]=45;env._update_reward()
torch.testing.assert_close(env._reward_buf,-env._best_mse)
env._pose_mse=original
env.reset(torch.tensor([0],device='cuda:0'))
torch.testing.assert_close(env._best_mse[0],env._pose_mse()[0])
assert abs(float(env._best_mse[1])-.08)<1e-6

obs,_=env.reset()
expected=env._pose_mse().clone();total=torch.zeros_like(expected)
for t in range(1,46):
    obs,reward,done,_=env.step(env._init_dof_pos.expand(64,-1))
    expected=torch.minimum(expected,env._pose_mse())
    assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
    torch.testing.assert_close(env._best_mse,expected)
    torch.testing.assert_close(obs[:,-1],torch.full((64,),1-t/45,device="cuda:0"),atol=1e-6,rtol=0)
    assert (done==(2 if t==45 else 0)).all()
    if t<45:assert not reward.any()
    total+=reward
torch.testing.assert_close(total,-expected)
report=dict(passed=True,worlds=64,steps=45,inputs=141,initial_included=True,
            retained_earlier_minimum=True,partial_reset_isolated=True,terminal_only=True,
            passive_best_mse=float(expected.mean()),physics_finite=True)
(train.ROOT/'best_pose_smoke.json').write_text(json.dumps(report,indent=2))
print('BEST_POSE_TEST_PASS',json.dumps(report),flush=True)
