import json,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
p=Path('Saved/Diagnostics/RunHandThigh');report={};captures={}
for tag in ['forearm_spin','forearm_spin_fixed']:
 d=json.loads((p/(tag+'.json')).read_text());assert not d['error'],d['error']
 rows=d['rows'];captures[tag]=rows;r={x['tick']:x for x in rows};steps=[]
 for t in range(187,219,2):
  a=r[t]['future'];b=r[t-2]['future'];v=np.array(a['hand_r']['p'])-a['lowerarm_r']['p'];v/=np.linalg.norm(v)
  rv=(R.from_quat(a['lowerarm_r']['q'])*R.from_quat(b['lowerarm_r']['q']).inv()).as_rotvec()
  steps.append(dict(tick=t,axial_deg=float(np.degrees(np.dot(rv,v))),rotation_deg=float(np.degrees(np.linalg.norm(rv)))))
 report[tag]=dict(steps=steps,axial_total_deg=sum(x['axial_deg'] for x in steps),max_axial_step_deg=max(abs(x['axial_deg']) for x in steps))
before=captures['forearm_spin'];after=captures['forearm_spin_fixed']
comparison={}
for phase in ['future','presented','mesh']:
 positions={bone:max(float(np.linalg.norm(np.array(a[phase][bone]['p'])-b[phase][bone]['p'])) for a,b in zip(before,after) if a['tick']>10) for bone in ['upperarm_r','lowerarm_r','hand_r']}
 hand_rotation=max(float(np.degrees((R.from_quat(a[phase]['hand_r']['q'])*R.from_quat(b[phase]['hand_r']['q']).inv()).magnitude())) for a,b in zip(before,after) if a['tick']>10)
 comparison[phase]=dict(max_position_change_cm=positions,max_hand_rotation_change_deg=hand_rotation)
assert comparison['future']['max_position_change_cm']['hand_r']<.001,comparison
assert comparison['future']['max_hand_rotation_change_deg']<.001,comparison
assert report['forearm_spin_fixed']['max_axial_step_deg']<25,report
traces=[]
for tag in captures:
 traces.append([t for s in (p/(tag+'_nn.jsonl')).read_text(encoding='utf-8-sig').splitlines() if s.strip() and (t:=json.loads(s))['actor']==captures[tag][0]['actor']])
comparison['max_nn_input_change']=max(float(np.max(np.abs(np.array(a['upper_input'])-b['upper_input']))) for a,b in zip(*traces))
report['comparison']=comparison
(p/'forearm_spin_verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:{j:v for j,v in value.items() if j!='steps'} for k,value in report.items()},indent=2))
