import json,math,re
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
p=Path('Saved/Diagnostics');d=json.loads((p/'SharedCalf-all.json').read_text());assert d['reason']=='Complete'
rr=d['rows'];events=[]
def gap(r,s):
 b=r['meshes']['PhysicalMesh'];c=b['calf_'+s];f=b['foot_'+s]
 off=np.array([-42.561031,.107739,.42919] if s=='l' else [42.561165,-.107729,-.429205])
 tip=np.array(c['p'])+Rotation.from_quat(c['q']).apply(off*np.array(c['s']))
 return float(np.linalg.norm(tip-f['p']))
for i,r in enumerate(rr):
 for m in r['meshes'].values():
  for bone in m.values():assert all(math.isfinite(v) for part in bone.values() for v in part)
 if i and i+1<len(rr) and r['attack']=='None' and rr[i-1]['attack']!='None':
  event={'tick':r['clock'],'attack':rr[i-1]['attack'],'mode':r['mode'],'gaps':{s:[gap(x,s) for x in rr[i-1:i+3]] for s in ('l','r')}}
  events.append(event)
print('FULL_SEQUENCE_EXITS',len(events))
for e in events:print(e)
(p/'SharedCalf-sequence-check.json').write_text(json.dumps(events,indent=2))
