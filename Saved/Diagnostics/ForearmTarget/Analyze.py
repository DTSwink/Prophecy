import json,pathlib,sys,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path(__file__).parent
result={}
for label in sys.argv[1:]:
 d=json.loads((p/f'capture_{label}.json').read_text());assert d['reason']=='Complete',d['reason']
 rs=[r for r in d['rows'] if r['actor'].endswith('_C_1') and r['t']>5]
 out={'samples_after_5s':len(rs),'end_seconds':rs[-1]['t'],'prediction':rs[0]['prediction'],'jolt':rs[0]['jolt'],'bones':{},'wrist_target_roll':{}}
 for bone in ['upperarm_r','lowerarm_r','hand_r','lowerarm_l','hand_l']:
  t=R.from_quat([r['bones'][bone]['target'] for r in rs]);q=R.from_quat([r['bones'][bone]['q'] for r in rs])
  out['bones'][bone]={'target_excursion_deg':float(np.degrees((t[0].inv()*t).magnitude()).max()),'physical_excursion_deg':float(np.degrees((q[0].inv()*q).magnitude()).max()),'max_target_error_deg':float(np.degrees((t.inv()*q).magnitude()).max())}
 for side in ['r','l']:
  q=(R.from_quat([r['bones']['lowerarm_'+side]['target'] for r in rs]).inv()*R.from_quat([r['bones']['hand_'+side]['target'] for r in rs])).as_quat()
  roll=np.unwrap(2*np.arctan2(q[:,0],q[:,3])); wrapped=(np.degrees(roll)+180)%360-180
  out['wrist_target_roll'][side]={'range_unwrapped_deg':float(np.ptp(np.degrees(roll))),'max_abs_wrapped_deg':float(np.abs(wrapped).max())}
 result[label]=out
print(json.dumps(result,indent=2));(p/'comparison.json').write_text(json.dumps(result,indent=2))
