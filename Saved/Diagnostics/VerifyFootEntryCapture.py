import json,numpy as np
from scipy.spatial.transform import Rotation as R
from pathlib import Path
d=json.loads(Path('Saved/Diagnostics/FootEntryInertia-runtime.json').read_text());rows=d['rows'];i=next(i for i,r in enumerate(rows) if r['triggered']);out={}
for bone in ['pelvis','foot_l','foot_r']:
 r=[x if bone=='pelvis' else x['bones'][bone] for x in rows]
 p=[np.array(x['target']['p']) for x in r];q=[R.from_quat(x['target']['q']) for x in r]
 out[bone]={'first_delta_error_cm':float(np.linalg.norm(p[i]-2*p[i-1]+p[i-2])), 'first_angular_delta_error_rad':float(np.linalg.norm(((q[i]*q[i-1].inv())*(q[i-1]*q[i-2].inv()).inv()).as_rotvec())), 'max_target_mesh_distance':max(float(np.linalg.norm(np.array(x['target']['p'])-x['physical']['p'])) for x in r[i:]),'max_target_mesh_angle':max(float(np.linalg.norm((R.from_quat(x['target']['q'])*R.from_quat(x['physical']['q']).inv()).as_rotvec())) for x in r[i:])}
print(json.dumps(out,indent=2));Path('Saved/Diagnostics/FootEntryInertia-verification.json').write_text(json.dumps(out,indent=2))
