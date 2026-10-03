import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R
from ReplayTemperedLeg import rot,clean,points,unit
p=pathlib.Path('Saved/Diagnostics');r={round(x['time']*60):x for x in map(json.loads,(p/'Pelvis360-baseline-nn.jsonl').read_text().splitlines()) if x['actor'].endswith('_C_1')}
for f in (361,363,365,367,369,371):
 x=r[f];pub=np.array(x['published_lower']);raw=clean(np.array(x['lower_input'][:41])+x['lower_delta'][:41]);h,k,a,t=points(pub,1);hr,kr,ar,tr=points(raw,1);axis=unit(a-h);p0=unit(kr-hr-axis*np.dot(kr-hr,axis));p1=unit(k-h-axis*np.dot(k-h,axis));ang=np.degrees(np.arctan2(np.dot(axis,np.cross(p0,p1)),np.dot(p0,p1)))
 print(f,'whole rot',np.degrees(R.from_matrix(rot(raw,34)@rot(pub,34).T).magnitude()),'pole about final axis',ang,'foot shift cm',np.linalg.norm(a-ar)*100,'calf raw final cm',np.linalg.norm(ar-kr)*100,np.linalg.norm(a-k)*100)
