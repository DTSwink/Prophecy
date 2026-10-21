"""Production reset: whole-pose endpoints, partial resets, unchanged velocity."""
import ast, math
from pathlib import Path
from unittest.mock import patch
import numpy as np
import torch
torch.set_num_threads(1)
tree=ast.parse(Path(__file__).with_name('perturbed_omni.py').read_text())
helper=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='blend_root_pose')
cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
reset=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_ref_state_init')
class Base:
    def _ref_state_init(self,ids): pass
scope=dict(torch=torch,Base=Base,math=math)
testcls=ast.ClassDef(name='Env',bases=[ast.Name(id='Base',ctx=ast.Load())],keywords=[],body=[reset],decorator_list=[])
exec(compile(ast.fix_missing_locations(ast.Module(body=[helper,testcls],type_ignores=[])),'production_reset','exec'),scope)
class Engine:
    def __init__(self):
        self.pos=torch.randn(5,3);self.rot=torch.tensor([[0.,0.,0.,1.]]).repeat(5,1)
        self.dof=torch.randn(5,34);self.velocity=torch.randn(5,40)
    def get_dof_pos(self,c):return self.dof
    def get_root_pos(self,c):return self.pos
    def get_root_rot(self,c):return self.rot
    def set_dof_pos(self,i,c,v):self.dof[i]=v
    def set_root_pos(self,i,c,v):self.pos[i]=v
    def set_root_rot(self,i,c,v):self.rot[i]=v
e=scope['Env']();engine=e._engine=Engine()
e._get_char_id=lambda:0;e._device='cpu';e._perturb_ready=True
e._perturbed_getup=torch.tensor([False,True,True,True,False])
e._perturbed_rows=e._perturbed_getup;e._recovery_rows=torch.ones(5,dtype=torch.bool)
e._getup_blend=True;e._getup_upper_half_probability=.5
e._pose_blend=torch.ones(5);e._random_pose_frame=torch.full((5,),-1)
e._reset_floor_lift=torch.zeros(5);e._limp_floor_support=None
e._yaw_degrees=torch.zeros(5)
with np.load(Path(__file__).resolve().parents[2]/'Saved/MimicKitEquipment/limp-inits/corpus.npz') as d:
    e._limp_dofs=torch.tensor(d['dof'])
    e._limp_root_pos=torch.tensor(d['root_position'])
    e._limp_root_rot=torch.tensor(d['root_quaternion_xyzw'])
old=[x.clone() for x in [engine.pos,engine.rot,engine.dof,engine.velocity]]
samples=torch.tensor([0,1,2]);alpha=torch.tensor([0.,.5,1.])
with patch.object(torch,'randint',return_value=samples),patch.object(torch,'rand',return_value=alpha):
    e._ref_state_init(torch.tensor([1,2,3]))
torch.testing.assert_close(engine.pos[1],old[0][1])
torch.testing.assert_close(engine.rot[1],old[1][1])
torch.testing.assert_close(engine.dof[1],old[2][1])
torch.testing.assert_close(engine.pos[3],e._limp_root_pos[2])
torch.testing.assert_close(engine.dof[3],e._limp_dofs[2])
assert abs(torch.dot(engine.rot[3],e._limp_root_rot[2])) > .999999
torch.testing.assert_close(engine.pos[2],(old[0][2]+e._limp_root_pos[1])/2)
torch.testing.assert_close(engine.rot.norm(dim=-1),torch.ones(5))
for value,before in zip([engine.pos,engine.rot,engine.dof,engine.velocity],old):
    torch.testing.assert_close(value[[0,4]],before[[0,4]])
torch.testing.assert_close(engine.velocity,old[3])
# Opposite quaternion signs must represent the same rotation throughout.
p,r=scope['blend_root_pose'](old[0],old[1],old[0],-old[1],torch.linspace(0,1,5))
torch.testing.assert_close(r,old[1])
e._ref_state_init(torch.tensor([],dtype=torch.long))
print('PASS: actual reset preserves untouched rows and velocities; alpha0 vanilla, alpha1 limp; whole-root midpoint, normalized rotation, antipodal and empty batches.')
# Verify exact cohort totals under the real evenly distributed assignment.
tree=ast.parse(Path(__file__).with_name('recovery_omni.py').read_text())
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='random_start_rows')
exec(compile(ast.Module(body=[node],type_ignores=[]),'cohorts','exec'),scope)
rows=torch.arange(512);motion=scope['random_start_rows'](rows,512,.5).long()
normal=rows[scope['random_start_rows'](rows,512,154/512,motion)]
random=scope['random_start_rows'](normal,512,.5,motion)
assert int(random.sum())==77
assert [(motion[normal]==i).sum().item() for i in (0,1)]==[77,77]
print('PASS: 154 normal /358 perturbed; front/back256 each; normal77 frame0/77 random.')
