"""Exercise the actual patched reset and done methods on CPU tensors."""
import ast
import json
import math
from pathlib import Path
from types import SimpleNamespace as NS
import torch
from getup_perturbed_plus import HELPER, test

ROOT=Path(__file__).resolve().parents[2]
tree=ast.parse(Path(__file__).with_name('perturbed_omni.py').read_text())
cls=next(x for x in tree.body if isinstance(x,ast.ClassDef))
methods=[x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name in ('_ref_state_init','_update_done')]
class Base:
    def _ref_state_init(self,ids):pass
    def _update_done(self):pass
ns=dict(torch=torch,math=math,RecoveryOmniEnv=Base,
    q=NS(quat_rotate=lambda rotation,v:v),
    DoneFlags=NS(NULL=NS(value=0),FAIL=NS(value=1),SUCC=NS(value=2),TIME=NS(value=3)),
    EnvMode=NS(TRAIN=1),
    com2_velocity=lambda v,m:torch.zeros((len(v),2)),
    com2_failure=lambda v,t,m:torch.zeros(len(v),dtype=torch.bool))
exec(HELPER,ns)
exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(name='PerturbedOmniEnv',bases=[ast.Name(id='RecoveryOmniEnv',ctx=ast.Load())],keywords=[],body=methods,decorator_list=[])],type_ignores=[])),'actual_methods','exec'),ns)
env=ns['PerturbedOmniEnv']();n=8
env._perturb_ready=True;env._device='cpu';env._get_char_id=lambda:0
env._perturbed_getup=torch.ones(n,dtype=torch.bool);env._perturbed_rows=env._perturbed_getup.clone();env._recovery_rows=env._perturbed_getup.clone()
env._perturbed_plus=torch.arange(n)%2==0
env._limp_dofs=None;env._loco_reset_dofs=torch.randn(100,12);env._loco_frame_pool=torch.arange(100)
env._getup_blend=False;env._random_pose_frame=torch.zeros(n,dtype=torch.long);env._yaw_degrees=torch.zeros(n);env._reset_floor_lift=torch.zeros(n)
env._plus_root_pool=torch.randn(100,3);env._plus_dof_pool=torch.randn(100,12);env._plus_max_spin=math.radians(700)
env._plus_linear_frame=torch.full((n,),-1,dtype=torch.long);env._plus_joint_frame=env._plus_linear_frame.clone()
env._plus_root_velocity=torch.zeros(n,3);env._plus_spin=torch.zeros(n,3);env._body_com=torch.ones(n,1,3)*.05
class Engine:
    def __init__(self):
        self.root=torch.zeros(n,3);self.spin=torch.zeros(n,3);self.dof=torch.zeros(n,12);self.pos=torch.zeros(n,1,3);self.pos[:,:,2]=.4
    def set_dof_pos(self,ids,c,v):pass
    def set_root_vel(self,ids,c,v):self.root[ids]=v
    def set_root_ang_vel(self,ids,c,v):self.spin[ids]=v
    def set_dof_vel(self,ids,c,v):self.dof[ids]=v
    def get_root_rot(self,c):return torch.tensor([0.,0.,0.,1.]).expand(n,4)
    def get_body_pos(self,c):return self.pos
    def get_body_vel(self,c):return torch.zeros(n,1,3)
env._engine=Engine();env._ref_state_init(torch.arange(n))
p=env._perturbed_plus;e=env._engine
assert (env._plus_linear_frame[p]!=env._plus_joint_frame[p]).all()
torch.testing.assert_close(e.root[p]-torch.cross(e.spin[p],env._body_com[p,0],dim=-1),env._plus_root_pool[env._plus_linear_frame[p]])
torch.testing.assert_close(e.dof[p],env._plus_dof_pool[env._plus_joint_frame[p]])
assert (e.root[~p]==0).all() and (e.dof[~p]==0).all() and (e.spin[~p]==0).all()
assert e.spin.norm(dim=-1).max()<=math.radians(700)
env._time_buf=torch.tensor([79,79,80,80,99,99,100,100])/30
env._getup_low_head_ticks=torch.where(p,100,80)
env._perturb_cfg=dict(getup_ticks=180,getup_low_head_failure_fraction=.5,min_speed_ratio=.7,grace_ticks=8,getup_failure_penalty=100.,getup_success_value=100.,getup_success_discount=.99)
env._episode_length=6;env._head_id=0;env._head_reset_height=torch.tensor([.9]);env._idle_head_height=torch.tensor([1.])
env._motion_ids=torch.zeros(n,dtype=torch.long);env._gaits=torch.tensor([-1]);env._success_feet_limit=None;env._com2_ids=[0];env._com2_masses=torch.ones(1);env._com2_targets=torch.zeros(1,2)
env._extremity_speed_enabled=False;env._pelvis_ceiling=None;env._mode=0;env._reset_reason=torch.zeros(n,dtype=torch.long);env._done_buf=torch.zeros(n,dtype=torch.long);env._reward_buf=torch.ones(n)
env._update_done()
assert env._done_buf.tolist()==[0,0,0,1,0,1,1,1]
assert env._reward_buf.tolist()==[1,1,1,-99,1,-99,-99,-99]
report=dict(**test(),actual_reset=True,unaffected_velocities_unchanged=True,actual_done_flags=env._done_buf.tolist(),actual_rewards=env._reward_buf.tolist())
(ROOT/'Saved/MimicKitEquipment/getup-plus-method-tests.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
