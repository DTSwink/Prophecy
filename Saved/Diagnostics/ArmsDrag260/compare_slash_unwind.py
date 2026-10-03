import json,math,sys,re
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
p=Path(__file__).parent
before,after=sys.argv[1:]
def read(tag):
 d=json.loads((p/(tag+'.json')).read_text());assert not d['error'],d['error']
 return {r['tick']:r for r in d['rows'] if r['player']}
a,b=read(before),read(after)
pos=left=fore=0.;steps=[]
for t,r in b.items():
 if t not in a:continue
 for field in ('future','presented'):
  for bone in r[field]:
   pos=max(pos,float(np.linalg.norm(np.array(r[field][bone]['p'])-a[t][field][bone]['p'])))
  for bone in ('hand_l','lowerarm_r'):
   diff=math.degrees((R.from_quat(r[field][bone]['q'])*R.from_quat(a[t][field][bone]['q']).inv()).magnitude())
   if bone=='hand_l':left=max(left,diff)
   else:fore=max(fore,diff)
 if t-1 in b:
  q=R.from_quat(r['presented']['hand_r']['q']);prev=R.from_quat(b[t-1]['presented']['hand_r']['q'])
  steps.append((math.degrees((q*prev.inv()).magnitude()),t))
lines=re.findall(r'WristSplit time=(\S+) weight=(\S+) yaw=(\S+) elevation=(\S+) idleElevation=(\S+) unwrapped=(\S+)',(p/(after+'.log')).read_text())
summary=dict(max_position_difference_cm=pos,max_left_wrist_difference_deg=left,max_forearm_difference_deg=fore,max_recovery_step=max((x for x in steps if 187<=x[1]<=307)),max_fade_step=max((x for x in steps if 277<=x[1]<=307)),route_samples=lines[::10],seed=re.findall(r'WristUnwind[^\n]*',(p/(after+'.log')).read_text()),final_steps=[x for x in steps if 301<=x[1]<=310])
(p/(after+'_comparison.json')).write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
