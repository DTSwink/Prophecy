import json,pathlib,math
root=pathlib.Path(__file__).parent
good=json.loads((root/'ThighOutward-20260920-170452/mechanism-audit.json').read_text())
bad=json.loads((root/'ThighOutward-20260920-165427/snap-mechanism.json').read_text())
print('STABLE BASELINE PEAKS')
for r in good['summary']['kicks'][:4]:
 print({k:round(r[k],4) for k in ('kick','time','distance_cm','actual_side_cm','transported_side_cm','full_guide_side_cm','toe_based_full_guide_side_cm','heading_disagreement_deg')})
print('SNAP PRECEDING FRAME AND FRAME')
for t in (4.483333066105843,6.549999609589577):
 rs=bad['frames'];i=min(range(len(rs)),key=lambda i:abs(rs[i]['time']-t))
 for r in rs[i-1:i+1]:print({k:r.get(k) for k in ('kick','time','z','hint_radius_cm','hint_sign','reflected','source_step_deg','source_upper_step_deg','axis_step_deg','guide_step_deg','foot_heading_step_deg')})
print('ATTACK CARRYOVER')
from ReplayTemperedLeg import points
import numpy as np
kick=0;was=False
for line in (root/'ThighOutward-20260920-170452/pipeline.jsonl').open():
 r=json.loads(line)
 if r['actor']!='BP_ProphecyManualPoseAgent_C_1':continue
 if r['attack'] and not was:
  kick+=1
  prev=np.array(r['previous_lower']);h,k,a,t=points(prev)
  if kick<=4:print(dict(kick=kick,time=r['time'],previous_ankle_to_hip_cm=float(np.linalg.norm(a-h)*100),pelvis_z_cm=prev[2]*100,ankle_z_cm=a[2]*100))
 was=r['attack']
