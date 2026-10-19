"""CPU numerical checks of the exact scripted reward helper, no simulator."""
import ast
from pathlib import Path
import torch

source=Path(__file__).with_name('absolute_walk.py').read_text()
node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='position_leeway_mse')
fn=torch.jit.CompilationUnit(ast.get_source_segment(source,node)+'\n').position_leeway_mse
legs=torch.tensor([True])
upper=torch.tensor([False])
def value(delta,mask):
    return fn(torch.tensor([[delta]],dtype=torch.float64),mask,.10,.05,.05)
def check(delta,mask,expected):
    torch.testing.assert_close(value(delta,mask),torch.tensor([expected],dtype=torch.float64),atol=1e-14,rtol=1e-10)

for axis in ([.08,0,0],[0,.08,0],[.10,0,.05],[0,-.10,-.05]):check(axis,legs,0.)
check([0,0,.08],legs,.03**2/3)
check([.13,0,.09],legs,(.03**2+.04**2)/3)
check([.08,.08,0],legs,((2*.08**2)**.5-.10)**2/3)
for axis in ([.05,0,0],[0,.05,0],[0,0,.05],[0,0,0]):check(axis,upper,0.)
check([.04,.04,0],upper,((2*.04**2)**.5-.05)**2/3)
check([0,0,-.08],upper,.03**2/3)
delta=torch.randn(512,15,3,dtype=torch.float64)
mask=torch.tensor([False]*9+[True]*6)
torch.testing.assert_close(fn(delta,mask,0.,0.,0.),delta.square().mean((1,2)))
torch.testing.assert_close(fn(-delta,mask,.10,.05,.05),fn(delta,mask,.10,.05,.05))
torch.testing.assert_close(fn(delta[:,:,[1,0,2]],mask,.10,.05,.05),fn(delta,mask,.10,.05,.05))
assert torch.all(fn(delta,mask,.10,.05,.05)<=delta.square().mean((1,2)))
print('PASS: Z vertical; XY radial leg allowance; isotropic upper allowance; boundary continuity; original denominator; zero allowance reproduces MSE.')

# Exercise the actual environment membership method with reordered motion IDs:
# recovery/normal idle share gait -1; walk and run must retain raw MSE exactly.
from types import SimpleNamespace
omni=ast.parse(Path(__file__).with_name('omni_walk.py').read_text())
cls=next(n for n in omni.body if isinstance(n,ast.ClassDef) and n.name=='OmniWalkEnv')
method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_position_leeway_rows')
ns={};exec(compile(ast.Module(body=[method],type_ignores=[]),'idle-mask','exec'),ns)
state=SimpleNamespace(_gaits=torch.tensor([-1.,0.,1.,-1.]),_motion_ids=torch.tensor([2,0,3,1]))
membership=ns['_position_leeway_rows'](state)
assert membership.tolist()==[False,True,True,False]
raw=delta[:4].square().mean((1,2));allowed=fn(delta[:4],mask,.10,.05,.05)
scoped=torch.where(membership,allowed,raw)
assert torch.equal(scoped[~membership],raw[~membership])
assert torch.equal(scoped[membership],allowed[membership])
print('PASS: idle/get-up membership only; walk/run MSE bit-identical to original.')

node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='spherical_position_mse')
sphere=torch.jit.CompilationUnit(ast.get_source_segment(source,node)+'\n').spherical_position_mse
for d in ([.03,0.,0.],[0.,-.03,0.],[0.,0.,.03]):
    torch.testing.assert_close(sphere(torch.tensor([[d]],dtype=torch.float64),.03),torch.zeros(1,dtype=torch.float64))
d=torch.tensor([[[.03,.04,0.]]],dtype=torch.float64)
torch.testing.assert_close(sphere(d,.03),torch.tensor([.02**2/3],dtype=torch.float64))
torch.testing.assert_close(sphere(delta,0.),delta.square().mean((1,2)))
scoped=torch.where(membership,allowed,sphere(delta[:4],.03))
assert torch.equal(scoped[membership],allowed[membership])
assert torch.equal(scoped[~membership],sphere(delta[:4],.03)[~membership])
print('PASS: locomotion 3cm radial allowance on XYZ, including diagonals; idle allowances unchanged.')
