"""CPU regression of the production cohort assignment and reset sampling."""
import ast
import math
from pathlib import Path
from types import SimpleNamespace
import torch

torch.set_num_threads(1)
tree = ast.parse(Path(__file__).with_name('recovery_omni.py').read_text())
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_reset_ref_motion')
helper = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'random_start_rows')
class Base:
    def _reset_ref_motion(self, ids): pass
def circular_phase(t): return torch.stack((torch.cos(2*math.pi*t), torch.sin(2*math.pi*t)), -1)
scope = dict(torch=torch, math=math, Base=Base, circular_phase=circular_phase)
testcls = ast.ClassDef(name='Env', bases=[ast.Name(id='Base', ctx=ast.Load())], keywords=[], body=[method], decorator_list=[])
exec(compile(ast.fix_missing_locations(ast.Module(body=[helper, testcls], type_ignores=[])), 'production_reset', 'exec'), scope)
e = scope['Env'](); n = 512; count = 292
ids = torch.floor((torch.arange(count)+.5)*307/count).long()
e._device='cpu'; e._recovery_ready=True; e._reset_after_getup=True
e._recovery_random_start_fraction=.5
e._recovery_random_start_rows=scope['random_start_rows'](ids,n,.5)
e._recovery_rows=torch.zeros(n,dtype=torch.bool); e._recovery_rows[ids]=True
e._recovery_motion=torch.zeros(n,dtype=torch.long)
e._recovery_start=torch.zeros(n); e._recovery_start_frame=torch.full((n,),-1,dtype=torch.long)
e._feedback_phase=torch.zeros(n,2); e._pending_phase=torch.zeros(n,2)
e._ref_dof_pos=torch.zeros(n,1); e._ref_joint_rot=torch.zeros(n,1)
counts=torch.tensor([43,47]); lengths=(counts-1)/30
e._recovery_lib=SimpleNamespace(_motion_num_frames=counts,get_motion_length=lambda m:lengths[m],joint_rot_to_dof=lambda j:j)
e._motion_lib=e._recovery_lib
e.recovery_active=lambda:e._recovery_rows
e._replace_recovery_reference=lambda:None
fixed=e._recovery_rows & ~e._recovery_random_start_rows
assert int(fixed.sum())==int(e._recovery_random_start_rows.sum())==146
seen=set()
for _ in range(25):
    e._reset_ref_motion(torch.arange(n))
    assert (e._recovery_start_frame[fixed]==0).all()
    assert (e._recovery_start_frame[~e._recovery_rows]==-1).all()
    frames=e._recovery_start_frame[ids]; motion=e._recovery_motion[ids]
    assert ((frames>=0)&(frames<counts[motion]-1)).all()
    torch.testing.assert_close(e._recovery_start[ids],frames/30)
    torch.testing.assert_close(e._feedback_phase[ids],circular_phase(e._recovery_start[ids]/lengths[motion]))
    torch.testing.assert_close(e._pending_phase,e._feedback_phase)
    seen.update(e._recovery_start_frame[e._recovery_random_start_rows].tolist())
assert len(seen)==46
before=e._recovery_start_frame.clone(); subset=ids[::3]
e._reset_ref_motion(subset)
untouched=torch.ones(n,dtype=torch.bool); untouched[subset]=False
assert torch.equal(before[untouched],e._recovery_start_frame[untouched])
assert not scope['random_start_rows'](ids,n,0.).any()
assert torch.equal(scope['random_start_rows'](ids,n,1.),e._recovery_rows)
print('PASS: 146 fixed frame-0 + 146 random-frame get-up rows; valid frames, matching phase, partial resets and legacy extremes.')
