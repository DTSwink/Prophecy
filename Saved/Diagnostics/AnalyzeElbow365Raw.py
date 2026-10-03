import pathlib,json,numpy as np
from scipy.spatial.transform import Rotation as R
src=pathlib.Path('Saved/Diagnostics/AnalyzePikeRawUpper.py').read_text().split('report={}')[0]
src=src.replace('upperarm_r','upperarm_l').replace('lowerarm_r','lowerarm_l').replace('clavicle_r','clavicle_l').replace('u[84:90]','u[69:75]').replace('u[75:78]','u[60:63]')
exec(src)
cap=json.loads((p/'elbow365_no_inertia.json').read_text())['rows']
for line in (p/'elbow365_no_inertia_nn.jsonl').read_text().splitlines():
 t=json.loads(line)
 if t['actor']!=cap[0]['actor'] or t['attack']:continue
 row=min(cap,key=lambda r:abs(r['t']-t['time']));tick=row['tick']
 if not 361<=tick<=373:continue
 v,q,qcl=decode(t);b=row['raw'];qr=lambda n:R.from_quat(b[n]['future']['q'])
 actual=qr('spine_05').inv()*qr('upperarm_l')
 print(tick,'raw S,E,H',np.round(v,3),'length',np.linalg.norm(v[2]-v[1]),'upper_vs_final',np.degrees((q.inv()*actual).magnitude()))
