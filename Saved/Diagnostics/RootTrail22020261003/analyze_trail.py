import json,numpy as np
from pathlib import Path
p=Path('Saved/Diagnostics/RootTrail22020261003/baseline.json')
if not p.exists():raise SystemExit('Capture still running')
z=json.loads(p.read_text());print(z['reason']);a={r['tick']:r for r in z['rows']}
print('smoothing',a[220]['smoothing'])
print('tick alpha raw first/end direction, continuous first/end direction, actor yaw')
from scipy.spatial.transform import Rotation as R
for t in range(208,241):
 r=a[t];w=np.array(r['window']);c=np.array([x['p'] for x in r['continuous']]);v=w[2:]-w[1];u=c[1:]-c[0]
 angles=np.degrees(np.arctan2(v[:,1],v[:,0]));ca=np.degrees(np.arctan2(u[:,1],u[:,0]));q=R.from_quat(r['actor_transform']['q']).as_euler('xyz',degrees=True)[2]
 print(t,r['alpha'],*(round(x,3) for x in [angles[0],angles[-1],ca[0],ca[-1],q]))
