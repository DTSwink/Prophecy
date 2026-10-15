import os,sys,json
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
root=Path('/workspace/mimickit_trial');sys.path.insert(0,str(root/'MimicKit/mimickit'))
import torch,yaml,numpy as np
from neutral_pose import body_position_mse, NeutralPoseEnv
from util import torch_util
from replay import geometry
from scipy.spatial.transform import Rotation

os.chdir(root/'MimicKit');torch.set_num_threads(1)
cfg=yaml.safe_load((root/'pipeline/neutral_pose_env.yaml').read_text())
engine=yaml.safe_load(Path('data/engines/newton_engine.yaml').read_text())
e=NeutralPoseEnv(cfg,engine,64,'cuda:0',False)
target=e._neutral_positions.cpu();root_pos=target[:,0,:].clone();identity=torch.tensor([[0.,0.,0.,1.]])
torch.testing.assert_close(body_position_mse(target,root_pos,identity,target),torch.zeros(1))
raised=target+torch.tensor([0.,0.,.3])
torch.testing.assert_close(body_position_mse(raised,root_pos+torch.tensor([0.,0.,.3]),identity,target),torch.tensor([.03]))
for yaw in [-2.,-.2,1.4]:
    q=torch_util.exp_map_to_quat(torch.tensor([[0.,0.,yaw]]))
    translated=torch_util.quat_rotate(q[:,None,:].expand(1,target.shape[1],4).reshape(-1,4),target.reshape(-1,3)).reshape_as(target)+torch.tensor([7.,-4.,0.])
    torch.testing.assert_close(body_position_mse(translated,translated[:,0],q,target),torch.zeros(1),atol=1e-10,rtol=0)
perturbed=target.clone();perturbed[0,2,0]+=.1
torch.testing.assert_close(body_position_mse(perturbed,root_pos,identity,target),torch.tensor([.01/target.shape[1]/3]))

# Verify the stock neutral pose actually places its original foot colliders on the floor.
pose=torch.tensor(cfg['neutral_pose'],device='cuda:0')[None,:]
pos,rot=e._kin_char_model.forward_kinematics(pose[:,:3],torch_util.exp_map_to_quat(pose[:,3:6]),e._kin_char_model.dof_to_rot(pose[:,6:]))
pos=pos[0].cpu().numpy();rot=Rotation.from_quat(rot[0].cpu().numpy()).as_matrix()
g=geometry(Path(cfg['char_file']));feet=[]
for shape in g['shapes']:
    if 'foot' not in shape['bone']:continue
    i=g['names'].index(shape['bone']);center=pos[i]+rot[i]@shape['position'];axes=rot[i]@np.array(shape['axes']).T
    bottom=center[2]-np.abs(axes[2])@(np.array(shape['dimensions'])/2)
    feet.append(float(bottom))
assert max(abs(v) for v in feet)<.001,feet
obs,_=e.reset();assert obs.shape==(64,141)
total=torch.zeros(64,device='cuda:0');initial_mse=e._pose_mse().mean().item()
for t in range(1,46):
    obs,reward,done,_=e.step(e._init_dof_pos.expand(64,-1))
    assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
    assert (done==(2 if t==45 else 0)).all()
    if t<45: assert not reward.any()
    total+=reward
torch.testing.assert_close(total,-e._pose_mse())
e.reset(torch.tensor([0,3],device='cuda:0'))
assert e._timestep_buf[0]==0 and e._timestep_buf[1]==45
e._continuous_reward=True
e.reset()
continuous_total=torch.zeros(64,device='cuda:0')
errors=[]
for t in range(1,46):
    obs,reward,done,_=e.step(e._init_dof_pos.expand(64,-1))
    error=e._pose_mse().clone()
    assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
    assert (done==(2 if t==45 else 0)).all()
    torch.testing.assert_close(reward,-error/45)
    if t==1: assert (reward<0).all(), 'Early pose error must contribute'
    continuous_total+=reward
    errors.append(error)
torch.testing.assert_close(continuous_total,-torch.stack(errors).mean(0))
report=dict(passed=True,worlds=64,steps=45,observations=141,body_count=target.shape[1],neutral_foot_bottom_m=feet,
    initial_supine_mse_m2=initial_mse,passive_final_mse_m2=-total.mean().item(),physics_graph=e._engine._graph is not None,
    continuous_reward_every_step_verified=True,continuous_episode_mean_mse_m2=-continuous_total.mean().item())
(root/'neutral_pose_smoke.json').write_text(json.dumps(report,indent=2));print('NEUTRAL_POSE_TEST_PASS',json.dumps(report),flush=True)
