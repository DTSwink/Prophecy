"""CPU-only check in the existing MimicKit environment; no trainer or GPU work."""
from pathlib import Path
import json
import importlib.metadata
import numpy as np
import warp as wp
import newton
import mujoco
import mujoco_warp as mjw
from scipy.spatial.transform import Rotation as R
from runtime import install_limits

HERE=Path(__file__).resolve().parent
wp.init();wp.set_device('cpu')
builder=newton.ModelBuilder()
newton.solvers.SolverMuJoCo.register_custom_attributes(builder)
builder.add_mjcf(str(HERE/'humanoid_uefn.xml'),floating=True,ignore_inertial_definitions=False,
                 collapse_fixed_joints=False,enable_self_collisions=True,convert_3d_hinge_to_ball_joints=True)
model=builder.finalize(device='cpu')
solver=newton.solvers.SolverMuJoCo(model,solver='newton',njmax=100,nconmax=50,iterations=30,ls_iterations=20)
print('JOINT_NAMES',[solver.mj_model.joint(i).name for i in range(solver.mj_model.njnt)],flush=True)
metadata=json.loads((HERE/'limits.json').read_text())
extension=install_limits(solver.mj_model,solver.mjw_model,metadata)
assert model.body_count==15 and solver.mj_model.nv==6+metadata['action_dimensions']
mjw.forward(solver.mjw_model,solver.mjw_data)
assert np.isfinite(solver.mjw_data.qpos.numpy()).all()
expected_locked=sum(j['modes'].count(2) for j in metadata['joints'] if j['kind']=='ball')
assert int(solver.mjw_data.ne.numpy()[0])==expected_locked
cpu_data=mujoco.MjData(solver.mj_model)
cpu_data.qpos[:]=solver.mjw_data.qpos.numpy()[0]
mujoco.mj_forward(solver.mj_model,cpu_data)
geometry_error=0.
for g in metadata['geometry']:
    ids=[i for i in range(solver.mj_model.ngeom) if solver.mj_model.geom(i).name==g['name']
         or solver.mj_model.geom(i).name.rsplit('/',1)[-1].rsplit('_',1)[0]==g['name']]
    assert len(ids)==1,(g['name'],ids)
    ident=ids[0]
    geometry_error=max(geometry_error,float(np.linalg.norm(cpu_data.geom_xpos[ident]-g['position'])))
    assert np.max(np.abs(cpu_data.geom_xmat[ident].reshape(3,3)-R.from_quat(g['quaternion']).as_matrix()))<2e-5
    assert np.max(np.abs(solver.mj_model.geom_size[ident,:len(g['size'])]-g['size']))<1e-6
assert geometry_error<2e-6,geometry_error
report=dict(passed=True,device='cpu',bodies=model.body_count,nv=solver.mj_model.nv,
            ball_profiles=len(extension.joints),locked_axis_rows=solver.mjw_data.ne.numpy().tolist(),
            collider_count=len(metadata['geometry']),max_collider_position_error_m=geometry_error,
            versions={n:importlib.metadata.version(n) for n in ('newton','mujoco','mujoco-warp','warp-lang')})
(HERE/'newton-validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2),flush=True)
