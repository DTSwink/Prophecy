"""GPU reset, reward, geometry and pre-optimization failure tests."""
import os,sys,json,math
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
root=Path('/workspace/mimickit_trial');sys.path.insert(0,str(root/'MimicKit/mimickit'))
import torch,yaml
from recovery_pose import RecoveryPoseEnv
from health import invalid_batch,install_guard
os.chdir(root/'MimicKit');torch.set_num_threads(1)
cfg=yaml.safe_load((root/'pipeline/recovery_pose_env.yaml').read_text())
engine=yaml.safe_load(Path('data/engines/newton_engine.yaml').read_text())
e=RecoveryPoseEnv(cfg,engine,128,'cuda:0',False)
obs,_=e.reset();char=e._get_char_id()
assert obs.shape==(128,141) and torch.isfinite(obs).all()
starts=e._starts_on_back.clone();back=int(starts.sum());assert 40<back<88,back
dofs=e._engine.get_dof_pos(char).clone()
assert (dofs-e._init_dof_pos).abs().max()<math.radians(5)+1e-6
assert float(dofs.std(dim=0).mean())>.01
bottom=e._lowest_geometry(e._engine.get_body_pos(char),e._engine.get_body_rot(char))
torch.testing.assert_close(bottom,torch.full_like(bottom,.002),atol=1e-6,rtol=0)
total=torch.zeros(128,device='cuda:0');mse=[]
for step in range(45):
    obs,reward,done,_=e.step(dofs)
    assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
    torch.testing.assert_close(reward,-e._pose_mse()/45)
    assert (done==(2 if step==44 else 0)).all()
    total+=reward;mse.append(e._pose_mse().clone())
torch.testing.assert_close(total,-torch.stack(mse).mean(0))
untouched=e._engine.get_body_pos(char)[1].clone()
e.reset(torch.tensor([0,3],device='cuda:0'))
torch.testing.assert_close(e._engine.get_body_pos(char)[1],untouched)
assert e._timestep_buf[0]==0 and e._timestep_buf[1]==45
# A bad sample must prevent optimization, identify timestep/world and preserve all finite input.
from types import SimpleNamespace
buf={'obs':torch.ones(32,128,141,device='cuda:0'),'reward':torch.ones(32,128,device='cuda:0')}
assert invalid_batch(buf) is None
buf['obs'][7,11,3]=float('nan');assert invalid_batch(buf)=={'obs':[[7,11]]}
a=SimpleNamespace(_rollout_train=lambda steps:None,_exp_buffer=SimpleNamespace(_buffers=buf));alerts=[]
install_guard(a,alerts.append)
try:a._rollout_train(32);raise AssertionError('invalid batch accepted')
except FloatingPointError:pass
assert len(alerts)==1
report=dict(passed=True,worlds=128,back=back,front=128-back,noise_degrees=5,continuous_mse_mean=float(-total.mean()),
    back_mse=float(-total[starts].mean()),front_mse=float(-total[~starts].mean()),min_floor_clearance=float(bottom.min()),
    invalid_batch_detected_before_optimization=True)
(root/'recovery_pose_smoke.json').write_text(json.dumps(report,indent=2));print('RECOVERY_POSE_PASS',json.dumps(report),flush=True)
