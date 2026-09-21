import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path(__file__).parent
def angle(q1,q2):return float(np.degrees((R.from_quat(q1).inv()*R.from_quat(q2)).magnitude()))
def rows(mode):
    data=json.loads((p/f'openloop_{mode}.json').read_text())
    assert data['reason']=='Complete'
    return [r for r in data['rows'] if r['actor'].endswith('_C_1') and r['t']>=1]
a,b=rows('current'),rows('free')
assert len(a)==len(b) and all(abs(x['t']-y['t'])<1e-6 for x,y in zip(a,b))
result={'samples':len(a),'start':a[0]['t'],'end':a[-1]['t'],'bones':{}}
native=json.loads((p/'native_current_parsed.json').read_text())
f=next(r for r in native if r['child']=='hand_r')
f1,f2=R.from_quat(f['f1']),R.from_quat(f['f2'])
for bone in ['upperarm_r','lowerarm_r','hand_r']:
    err=lambda rows:[angle(r['bones'][bone]['q'],r['bones'][bone]['target']) for r in rows]
    result['bones'][bone]={'current_max_error':max(err(a)),'free_max_error':max(err(b)),
      'max_physical_difference':max(angle(x['bones'][bone]['q'],y['bones'][bone]['q']) for x,y in zip(a,b)),
      'max_target_difference':max(angle(x['bones'][bone]['target'],y['bones'][bone]['target']) for x,y in zip(a,b))}
for mode,rs in [('current',a),('free',b)]:
    angles=[]
    for r in rs:
        q=((R.from_quat(r['bones']['lowerarm_r']['q'])*f1).inv()*(R.from_quat(r['bones']['hand_r']['q'])*f2)).as_quat()
        angles.append((np.degrees(2*np.arctan2(q[0],q[3]))+180)%360-180)
    result[mode+'_max_abs_wrist_twist']=max(abs(float(v)) for v in angles)
    result[mode+'_wrist_limits']=rs[-1]['limits']['hand_r']
(p/'openloop_analysis.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
