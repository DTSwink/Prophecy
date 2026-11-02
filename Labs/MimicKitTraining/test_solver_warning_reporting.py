"""Execute the real warning callback with bounded and legacy diagnostics."""
import ast,json,sys,time
from pathlib import Path
from types import SimpleNamespace

path=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).with_name('train.py')
tree=ast.parse(path.read_text())
function=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='report_solver_warning')
logged=[];saved=[]
writer=SimpleNamespace(add_scalar=lambda *args:logged.append(args),flush=lambda:None)
agent=SimpleNamespace(_logger=SimpleNamespace(_writer=writer),_sample_count=123,_iter=4)
scope=dict(agent=agent,iteration_offset=20,time=time,json=json,directory=Path('.'),a=SimpleNamespace(name='callback-test'),atomic_json=lambda p,d:saved.append(d.copy()))
exec(compile(ast.Module(body=[function],type_ignores=[]),str(path),'exec'),scope)
scope['report_solver_warning'](dict(reason='fixed iteration profile',maximum_motor_residual_nm=1.25))
assert logged==[('health/solver_motor_residual_nm',1.25,123)],logged
assert saved[-1]['iteration']==24
logged.clear()
scope['report_solver_warning'](dict(roundoff_total=2,convergence_total=3,maximum_motor_residual_nm=.1,maximum_contact_limit_velocity_residual=.2))
assert [v[:2] for v in logged]==[
    ('health/solver_roundoff_warnings',2),('health/solver_convergence_warnings',3),
    ('health/solver_motor_residual_nm',.1),('health/solver_contact_limit_velocity_residual',.2)]
print('PASS: bounded report and all legacy solver metrics reach the writer')
