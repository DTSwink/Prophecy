"""Bake-job for the tiny shear not representable by UE's grip FTransform."""
import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
root=Path(__file__).resolve().parents[2]
s=json.loads((root/'Saved/SlashChain/sword_preview.json').read_text())['sword']
source=np.array(s['local_to_hand_source']).reshape(4,4)
exact=np.array(s['mesh_to_source_axes']) @ source[:3,:3] @ np.diag([1,-1,1])
trs=np.diag(s['scale']) @ Rotation.from_quat(s['quaternion_xyzw']).as_matrix().T
# v * residual * TRS == v * sourceLinear (row-vector convention).
residual=exact @ np.linalg.inv(trs)
assert np.max(np.abs(residual @ trs-exact))<1e-12
out=root/'Saved/Sword/exact_mesh_job.json';out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps({'basis':residual.tolist(),'source':s,'matrix_error':float(np.max(np.abs(residual@trs-exact)))},indent=2))
print(out)
print('Residual basis:',residual.tolist())
