"""Fixed-heading MSE contract, actual physics and replay accounting."""
import os,sys,json,tempfile
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
root=Path('/workspace/mimickit_trial')
sys.path.insert(0,str(root/'MimicKit/mimickit'))
import torch,numpy as np,yaml
from util import torch_util
from world_pose import WorldPoseEnv,world_pose_mse
from observe import Recorder
from replay import convert,geometry

torch.set_num_threads(1)
worst='--worst-body' in sys.argv
target=json.loads((root/'pipeline/amp_standing_target.json').read_text())
os.chdir(root/'MimicKit')
config=dict(env_name='world_pose',char_file='data/assets/humanoid/humanoid.xml',
    camera_mode='track',episode_length=2.,global_obs=True,root_height_obs=True,
    init_pose=target['pose'],target_pose=target['pose'],
    key_bodies=['head','right_hand','left_hand','right_foot','left_foot'],
    reset_seed=20261014,reset_joint_noise_degrees=5.,reset_floor_clearance_m=.002,worst_body=worst)
engine=yaml.safe_load(Path('data/engines/newton_engine.yaml').read_text())
env=WorldPoseEnv(config,engine,512,'cuda:0',False)
pos,rot=env._target_positions,env._target_rotations
zero=world_pose_mse(pos,rot,pos,rot)
torch.testing.assert_close(zero,torch.zeros_like(zero),atol=1e-10,rtol=0)
torch.testing.assert_close(world_pose_mse(pos+torch.tensor([3.,-2.,0.],device='cuda:0'),rot,pos,rot),zero,atol=1e-10,rtol=0)
for axis in range(3):
    angle=torch.zeros(3,device='cuda:0');angle[axis]=1.
    turn=torch_util.exp_map_to_quat(angle).expand_as(rot)
    assert world_pose_mse(torch_util.quat_rotate(turn,pos),torch_util.quat_mul(turn,rot),pos,rot).min()>1e-4
torch.testing.assert_close(world_pose_mse(pos,-rot,pos,rot),zero,atol=1e-10,rtol=0)
raised=world_pose_mse(pos+torch.tensor([0.,0.,.3],device='cuda:0'),rot,pos,rot)
torch.testing.assert_close(raised,torch.tensor([[.03,0]],device='cuda:0'),atol=1e-7,rtol=0)
# Different bodies own the largest position and rotation errors. The loss must
# pick the maximum COMBINED body, not sum unrelated maxima or average bodies.
bad_pos=pos.clone();bad_pos[:,1,2]+=3.
bad_rot=rot.clone();turn=torch.tensor([0.,0.,1.,0.],device='cuda:0')
bad_rot[:,2]=torch_util.quat_mul(turn.expand_as(rot[:,2]),rot[:,2])
torch.testing.assert_close(world_pose_mse(bad_pos,bad_rot,pos,rot,True),torch.tensor([[3.,0.]],device='cuda:0'))
bad_pos[:,1,2]=pos[:,1,2]
torch.testing.assert_close(world_pose_mse(bad_pos,bad_rot,pos,rot,True),torch.tensor([[0.,8/9]],device='cuda:0'))
torch.testing.assert_close(world_pose_mse(pos,rot,pos,rot,True),zero)
obs,_=env.reset();char=env._get_char_id()
assert obs.shape==(512,140) and not hasattr(env,'_disc_obs_buf')
back=int(env._starts_on_back.sum());assert 180<back<330
# All body orientation slots really carry world rotations, not local joints.
world=env._engine.get_body_rot(char)
torch.testing.assert_close(obs[:,1:7],torch_util.quat_to_tan_norm(world[:,0]),atol=1e-6,rtol=1e-5)
torch.testing.assert_close(obs[:,13:97],torch_util.quat_to_tan_norm(world[:,1:]).flatten(1),atol=1e-6,rtol=1e-5)
with tempfile.TemporaryDirectory() as directory:
    recorder=Recorder(env,directory);recorder.start()
    sums=torch.zeros((512,2),device='cuda:0')
    for tick in range(60):
        obs,reward,done,info=env.step(env._init_dof_pos.expand(512,-1))
        expected=world_pose_mse(env._engine.get_body_pos(char),env._engine.get_body_rot(char),pos,rot,worst)/60
        torch.testing.assert_close(env.loss_terms,expected)
        torch.testing.assert_close(reward,-expected.sum(-1))
        sums+=expected
        assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
        assert (done==(3 if tick==59 else 0)).all()
    measured=env.take_completed_losses()
    for i,name in enumerate(env.loss_term_names):
        assert abs(measured[name]-float(sums[:,i].mean()))<1e-6
    recorder.finish(0,0,dict(training_action_noise_std=.05,rollout_action_noise_std=0.))
    capture=convert(Path(directory)/'replay.npz',geometry(Path(config['char_file'])),'test')
    raw=np.load(Path(directory)/'replay.npz')
    assert json.loads(str(raw['metadata'].item()))['body_reduction']==('maximum_combined_error' if worst else 'mean')
    losses=capture['metadata']['evaluation']['frame_losses']
    assert set(losses)=={'position_mse','orientation_mse','total'}
    for tick in range(61):assert abs(losses['total'][tick]-losses['position_mse'][tick]-losses['orientation_mse'][tick])<1e-6
    assert len(capture['positions'][0])==61
env.reset(torch.tensor([0],device='cuda:0'));assert env._episode_losses[0].abs().max()==0
assert env._episode_losses[1:].abs().max()>0
report=dict(passed=True,worst_body=worst,same_body_components_verified=True,worlds=512,back=back,front=512-back,inputs=140,
    all_orientation_inputs_world=True,zero_target_error=True,xy_translation_invariant=True,
    yaw_pitch_roll_penalized=True,quaternion_sign_invariant=True,episode_ticks=60,
    equal_weighted_terms=True,reward_matches_mean_mse=True,replay_terms_verified=True,no_discriminator=True)
(root/('worst-body-smoke.json' if worst else 'world-pose-smoke.json')).write_text(json.dumps(report,indent=2))
print('WORLD_POSE_PASS',json.dumps(report),flush=True)
