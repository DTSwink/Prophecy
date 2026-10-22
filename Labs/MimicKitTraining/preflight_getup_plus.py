"""Run on the existing recovery GPU before the trainer is relaunched."""
import os,sys,json,zipfile
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial')
with zipfile.ZipFile(ROOT/'source.zip') as z:z.extractall(ROOT)
os.environ['PYGLET_HEADLESS']='true'
sys.path[:0]=[str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')]
import torch,warp as wp,yaml
from util import mp_util,torch_util as q
from perturbed_omni import PerturbedOmniEnv
torch.set_num_threads(1);torch.set_num_interop_threads(1)
wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6769)
os.chdir(ROOT/'MimicKit')
cfg=yaml.safe_load((ROOT/'prepared/env_config.yaml').read_text())
ec=yaml.safe_load((ROOT/'prepared/engine_config.yaml').read_text())
env=PerturbedOmniEnv(cfg,ec,1024,'cuda:0',False)
env.reset();p=env._perturbed_plus;char=env._get_char_id();e=env._engine
assert int(p.sum())==358 and int(env._perturbed_getup.sum())==717
assert int((~env._perturbed_rows).sum())==307
assert (env._plus_linear_frame[p]!=env._plus_joint_frame[p]).all()
spin=e.get_root_ang_vel(char)[p]
assert spin.norm(dim=-1).max()<=700*torch.pi/180+1e-5
origin=e.get_body_vel(char)[p,0]-torch.cross(e.get_body_ang_vel(char)[p,0],q.quat_rotate(e.get_body_rot(char)[p,0],env._body_com[p,0]),dim=-1)
torch.testing.assert_close(origin,env._plus_root_velocity[p],atol=2e-5,rtol=2e-5)
torch.testing.assert_close(e.get_dof_vel(char)[p],env._motion_lib._frame_dof_vel[env._plus_joint_frame[p]],atol=1e-5,rtol=1e-5)
assert (env._getup_low_head_ticks[p]==100).all() and (env._getup_low_head_ticks[~p]==80).all()
groups=[dict(motion=int(m),normal=int(((env._recovery_fixed_motion==m)&~env._perturbed_rows).sum()),ordinary=int(((env._recovery_fixed_motion==m)&env._perturbed_getup&~p).sum()),plus=int(((env._recovery_fixed_motion==m)&p).sum())) for m in torch.unique(env._recovery_fixed_motion)]
report=dict(worlds=1024,normal=307,ordinary_perturbed=359,perturbed_plus=358,groups=groups,
    different_frames=True,velocity_forward_kinematics_verified=True,head_thresholds_verified=True,
    spin_range_deg_s=[float(spin.norm(dim=-1).min()*180/torch.pi),float(spin.norm(dim=-1).max()*180/torch.pi)])
(ROOT/'getup-plus-preflight.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
