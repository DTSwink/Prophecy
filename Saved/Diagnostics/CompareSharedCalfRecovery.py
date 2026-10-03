import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
p=Path('Saved/Diagnostics')
def read(name):
 d=json.loads((p/name).read_text());assert d['reason']=='Complete',d['reason']
 return {r['clock']:r for r in d['rows'] if r['possessed']}
def metric(row,side):
 b=row['meshes']['PhysicalMesh'];c,f=b['calf_'+side],b['foot_'+side]
 off=np.array([-42.561031,.107739,.42919] if side=='l' else [42.561165,-.107729,-.429205])
 tip=np.array(c['p'])+Rotation.from_quat(c['q']).apply(off*np.array(c['s']))
 return {'length':float(np.linalg.norm(np.array(c['p'])-f['p'])),'gap':float(np.linalg.norm(tip-f['p'])),'scale':c['s']}
b=read('SharedCalf-baseline.json');a=read('SharedCalf-paired.json')
pre=max(np.linalg.norm(np.array(b[t]['meshes']['PhysicalMesh'][bone]['p'])-a[t]['meshes']['PhysicalMesh'][bone]['p']) for t in range(1380,1494) for bone in b[t]['meshes']['PhysicalMesh'])
print('PRE_HANDOFF_MAX_POSITION_DIFFERENCE_CM',pre)
result={'pre_difference_cm':float(pre),'samples':{}}
for t in (1493,1494,1495,1496,1500,1510,1524,1553,1554,1555):
 result['samples'][t]={side:{'before':metric(b[t],side),'after':metric(a[t],side)} for side in ('l','r')}
 print(t,json.dumps(result['samples'][t]))
for side in ('l','r'):
 old=abs(metric(b[1495],side)['gap']-metric(b[1494],side)['gap'])
 new=abs(metric(a[1495],side)['gap']-metric(a[1494],side)['gap'])
 print('FIRST_TICK_GAP_CHANGE',side,old,new)
 assert new<.1,(side,new)
 assert max(abs(x-y) for x,y in zip(metric(a[1494],side)['scale'],metric(a[1495],side)['scale']))<.001
assert pre<.03,pre
(p/'SharedCalf-comparison.json').write_text(json.dumps(result,indent=2))
print('PAIRED_CALF_RECOVERY_CHECK_PASSED')
