"""Exercise production termination with different head/hand and foot radii on CPU."""
import ast, math
from pathlib import Path
from types import SimpleNamespace
import torch

torch.set_num_threads(1)
tree=ast.parse(Path(__file__).with_name('recovery_omni.py').read_text())
cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
init=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_build_sim_tensors')
start=next(i for i,n in enumerate(init.body) if isinstance(n,ast.Assign) and ast.unparse(n.targets[0])=='self._recovery_target_radius_m')
end=next(i for i,n in enumerate(init.body[start:],start) if isinstance(n,ast.If) and '_recovery_pelvis_velocity_multiplier' in ast.unparse(n.test))
class Base:
    def _update_done(self): self._done_buf.fill_(0)
scope=dict(torch=torch,math=math,Base=Base,DoneFlags=SimpleNamespace(TIME=SimpleNamespace(value=3),SUCC=SimpleNamespace(value=2),NULL=SimpleNamespace(value=0),FAIL=SimpleNamespace(value=1)))
method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_update_done')
testcls=ast.ClassDef(name='Env',bases=[ast.Name(id='Base',ctx=ast.Load())],keywords=[],body=[method],decorator_list=[])
exec(compile(ast.fix_missing_locations(ast.Module(body=[testcls],type_ignores=[])),'production_done','exec'),scope)
env=scope['Env']();env._device='cpu';env.target_radius_m=.27
names=['head','right_hand','left_hand','right_foot','left_foot']
env._recovery_target_bodies=names;env._recovery_target_indices=list(range(5))
scope.update(self=env,names=names,cfg=dict(target_radius_m=.65,target_radii_m={'left_foot':.35,'right_foot':.35}))
exec(compile(ast.Module(body=init.body[start:end],type_ignores=[]),'production_radius','exec'),scope)
env._recovery_ready=True;env._recovery_ids=torch.arange(7);env._get_char_id=lambda:0
env._recovery_timeout_only=False;env._recovery_sphere_only=True;env._episode_length=10.
env._reset_after_getup=True;env._time_buf=torch.ones(7);env.recovery_active=lambda:torch.tensor([True]*6+[False])
env._done_buf=torch.zeros(8,dtype=torch.int32)
# At 32 cm each hand/head fails, either foot survives; at 36 cm a foot fails.
env.target_distances_sq=torch.zeros(8,5)
for i in range(5):env.target_distances_sq[i,i]=(.66 if i<3 else .32)**2
env.target_distances_sq[5,4]=.36**2
env._update_done()
assert env._done_buf.tolist()==[1,1,1,0,0,1,2,0],env._done_buf
assert env.target_radius_m==.27
scope['cfg']={'target_radius_m':.30}
exec(compile(ast.Module(body=init.body[start:end],type_ignores=[]),'default_radius','exec'),scope)
env._update_done()
assert env._done_buf.tolist()==[1,1,1,1,1,1,2,0]
print('PASS: 66cm head/hands fail; 32cm feet survive; 36cm feet fail; clip end resets; ordinary radius unchanged; legacy uniform radii preserved.')
