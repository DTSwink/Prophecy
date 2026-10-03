import json,numpy as np
from pathlib import Path
p=Path('Saved/Diagnostics');same=json.loads((p/'Leg920Fixed-same-frame.json').read_text());before=same['before'];after=same['after']
def pos(d,n):return np.array(d[n]['target']['p'])
def geom(d,side):
 h,k,f=[pos(d,n+'_'+side) for n in ('thigh','calf','foot')];u=k-h;v=f-k
 return dict(bend=float(np.degrees(np.arccos(np.clip(np.dot(u,v)/np.linalg.norm(u)/np.linalg.norm(v),-1,1)))),lengths=[float(np.linalg.norm(u)),float(np.linalg.norm(v))])
res={'same_frame':{}}
for side in ('l','r'):
 a=geom(before,side);b=geom(after,side)
 shift=pos(after,'foot_'+side)-pos(before,'foot_'+side)
 res['same_frame'][side]=dict(before=a,after=b,foot_shift=shift.tolist(),foot_shift_cm=float(np.linalg.norm(shift)),foot_rotation_unchanged=after['foot_'+side]['target']['q']==before['foot_'+side]['target']['q'])
res['pelvis_unchanged']=before['pelvis']==after['pelvis']
base={r['clock']:r for r in json.loads((p/'Leg920-capture.json').read_text())['rows']}
trial=json.loads((p/'Leg920Fixed-capture.json').read_text());res['reason']=trial['reason']
res['prefix_max_position_error']=max(np.linalg.norm(np.array(r['targets'][n][kind]['p'])-base[r['clock']]['targets'][n][kind]['p']) for r in trial['rows'] if r['clock']<=920 for n in r['targets'] for kind in ('previous','future','target'))
res['window']=[]
for r in trial['rows']:
 if 918<=r['clock']<=929:
  res['window'].append(dict(tick=r['clock'],bend=geom(r['targets'],'r')['bend'],pelvis_delta=float(np.linalg.norm(pos(r['targets'],'pelvis')-pos(base[r['clock']]['targets'],'pelvis')))))
(p/'Leg920Fixed-verification.json').write_text(json.dumps(res,indent=2))
print(json.dumps(res,indent=2))
