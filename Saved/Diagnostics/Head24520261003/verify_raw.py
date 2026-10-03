import json,numpy as np
from scipy.spatial.transform import Rotation as R
from pathlib import Path
p=Path('Saved/Diagnostics/Head24520261003')
a={r['tick']:r for r in json.loads((p/'raw_nn.json').read_text())['rows']}
b={r['tick']:r for r in json.loads((p/'baseline.json').read_text())['rows']}
trace=[json.loads(s) for s in (p/'raw_nn-inputs.jsonl').read_text().splitlines()]
meta=json.loads(Path('Content/locomotion/NN/prophecy_upper_body_runtime.json').read_text());print('cores',meta['core_bones'])
parents=dict(zip(['spine_01','spine_02','spine_03','spine_04','spine_05','neck_01','neck_02','head'],['pelvis','spine_01','spine_02','spine_03','spine_04','spine_05','neck_01','neck_02']))
mirror=np.diag([1,-1,1]);errs=[];rows=[]
for z in trace:
 if z['actor']!='BP_ProphecyManualPoseAgent_C_0':continue
 t=min(a,key=lambda t:abs(a[t]['time']-z['time']));r=a[t]
 vals=(np.array(z['upper_input'][90:180],dtype=np.float32)+np.array(z['upper_delta'],dtype=np.float32)).astype(float)
 errors=[]
 for name,par in parents.items():
  i=meta['core_bones'].index(name);v=vals[i*6:i*6+6];x=v[:3]/np.linalg.norm(v[:3]);y=v[3:]-x*np.dot(x,v[3:]);y/=np.linalg.norm(y)
  rot=R.from_matrix(mirror@np.array([x,y,np.cross(x,y)]).T@mirror)
  actual=R.from_quat(r['bones'][par]['future']['q']).inv()*R.from_quat(r['bones'][name]['future']['q'])
  errors.append(float(np.degrees((rot*actual.inv()).magnitude())))
 err=max(errors);errs.append(err)
 row=dict(tick=t,max_core_error_deg=err,upper_inference=z['upper_inference'],gaze=z['upper_input'][-2:]);rows.append(row)
 print(row)
prefix=max(np.linalg.norm(np.array(a[t]['bones']['head']['presented']['p'])-b[t]['bones']['head']['presented']['p']) for t in a if t in b)
result=dict(max_error_deg=max(errs),matching_replay_max_head_error_cm=float(prefix),rows=rows)
(p/'raw-parity.json').write_text(json.dumps(result,indent=2))
