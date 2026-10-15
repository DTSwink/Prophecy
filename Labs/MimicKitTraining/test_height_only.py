"""Actual-physics check: height-only loss never calls the body-pose calculation."""
import os,sys,json,tempfile
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
root=Path('/workspace/mimickit_trial')
sys.path.insert(0,str(root/'MimicKit/mimickit'))
import torch,numpy as np,yaml
import world_pose
from observe import Recorder
from replay import convert,geometry

torch.set_num_threads(1)
config=yaml.safe_load((root/'runs/20261014_175757_pose_height_bands_512/env_config.yaml').read_text())
config['height_bands_only']=True
engine=yaml.safe_load((root/'runs/20261014_175757_pose_height_bands_512/engine_config.yaml').read_text())
os.chdir(root/'MimicKit')
env=world_pose.WorldPoseEnv(config,engine,512,'cuda:0',False)
def forbidden(*args,**kwargs):raise AssertionError('Pose MSE must not be evaluated')
world_pose.world_pose_mse=forbidden
assert env.loss_term_names==('head_height_band','pelvis_height_band')
assert list(env.loss_weights.values())==config['height_band_weights']
obs,_=env.reset();assert obs.shape==(512,140)
target=env._target_positions[:,env._height_body_ids,2]
with tempfile.TemporaryDirectory() as directory:
    recorder=Recorder(env,directory);recorder.start()
    sums=torch.zeros((512,2),device='cuda:0')
    for tick in range(60):
        obs,reward,done,_=env.step(env._init_dof_pos.expand(512,-1))
        heights=env._engine.get_body_pos(env._get_char_id())[:,env._height_body_ids,2]
        expected=torch.maximum(.8*target-heights,heights-1.1*target).clamp_min(0).square()*env._height_weights/60
        torch.testing.assert_close(env.loss_terms,expected)
        torch.testing.assert_close(reward,-expected.sum(-1))
        sums+=expected
        assert torch.isfinite(obs).all() and (done==(3 if tick==59 else 0)).all()
    measured=env.take_completed_losses()
    for i,name in enumerate(env.loss_term_names):assert abs(measured[name]-float(sums[:,i].mean()))<1e-6
    recorder.finish(0,0,dict(training_action_noise_std=.05,rollout_action_noise_std=0.))
    replay=convert(Path(directory)/'replay.npz',geometry(Path(config['char_file'])),'height-only-test')
    meta=replay['metadata']['evaluation'];losses=meta['frame_losses']
    assert meta['body_reduction']=='none' and 'no body pose MSE' in meta['objective']
    assert set(losses)=={'head_height_band','pelvis_height_band','total'}
    np.testing.assert_allclose(losses['total'],np.array(losses['head_height_band'])+losses['pelvis_height_band'],atol=1e-7)
env.reset(torch.tensor([0],device='cuda:0'))
assert env._episode_losses[0].abs().max()==0 and env._episode_losses[1:].abs().max()>0
report=dict(passed=True,worlds=512,inputs=140,ticks=60,pose_mse_never_called=True,
    exact_height_weights=config['height_band_weights'],reward_accounting=True,replay_two_terms=True,partial_reset=True)
(root/'height-only-smoke.json').write_text(json.dumps(report,indent=2))
print('HEIGHT_ONLY_PASS',json.dumps(report),flush=True)
