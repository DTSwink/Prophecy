import json,math
import numpy as np
from scipy.spatial.transform import Rotation as R
from pathlib import Path
p=Path('Saved/Diagnostics/AttackStartInertia-runtime.json');d=json.loads(p.read_text());rows=d['rows'];i=next(i for i,r in enumerate(rows) if r['triggered']);post=rows[i:]
def delta(a,b):return R.from_quat(a)*R.from_quat(b).inv()
def raw(r):
 a=R.from_quat(r['previous']['q']);b=R.from_quat(r['future']['q']);v=(b*a.inv()).as_rotvec();angle=np.linalg.norm(v);t=r['alpha']
 w=math.atan2(t*math.sin(angle),(1-t)+t*math.cos(angle)) if angle>1e-12 else 0
 return R.from_rotvec(v*(w/angle if angle>1e-12 else 0))*a
out={'reason':d['reason'],'samples':len(rows),'first_translation_delta_error_cm':float(np.linalg.norm(np.array(rows[i]['target']['p'])-2*np.array(rows[i-1]['target']['p'])+rows[i-2]['target']['p'])),
 'first_angular_delta_error_radians':float(np.linalg.norm((delta(rows[i]['target']['q'],rows[i-1]['target']['q'])*delta(rows[i-1]['target']['q'],rows[i-2]['target']['q']).inv()).as_rotvec())),
 'maximum_physical_target_position_error_cm':max(float(np.linalg.norm(np.array(r['physical']['p'])-r['target']['p'])) for r in post),
 'maximum_physical_target_rotation_error_radians':max(float(np.linalg.norm(delta(r['physical']['q'],r['target']['q']).as_rotvec())) for r in post),
 'rotation_offset_degrees_by_tick':[float(np.linalg.norm((R.from_quat(r['target']['q'])*raw(r).inv()).as_rotvec())*180/math.pi) for r in post[:8]],
 'translation_offset_cm_by_tick':[float(np.linalg.norm(np.array(r['target']['p'])-((1-r['alpha'])*np.array(r['previous']['p'])+r['alpha']*np.array(r['future']['p'])))) for r in post[:8]]}
Path('Saved/Diagnostics/AttackStartInertia-verification.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
