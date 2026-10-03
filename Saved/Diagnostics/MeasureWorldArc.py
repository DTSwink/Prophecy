import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
p=Path('Saved/Diagnostics/ArmReach')
d=json.loads((p/'detect_world_arc.json').read_text())['rows']
def metrics(x):
 x=np.array(x);v=x[-1]-x[0];u=np.clip((x-x[0])@v/max(v@v,1e-12),0,1)
 distances=np.linalg.norm(x-x[0]-u[:,None]*v,axis=1)
 return dict(chord=float(np.linalg.norm(v)),length=float(np.linalg.norm(np.diff(x,axis=0),axis=1).sum()),deviation=float(distances.max()),peak_index=int(distances.argmax()))
result=[]
for i,a in enumerate(d):
 if i==0 or a['attack']!='None' or d[i-1]['attack']=='None':continue
 end=next((j for j in range(i+1,len(d)) if d[j]['attack']!='None'),len(d))
 rows=d[i:end]
 if len(rows)<40:continue
 item=dict(start=a['tick'],end=rows[-1]['tick'])
 for kind in ('presented','future'):
  h=np.array([r['pose']['hand_r'][kind]['p'] for r in rows]);m=dict(world=metrics(h))
  for ref in ('pelvis','spine_05'):
   pos=np.array([r['pose'][ref][kind]['p'] for r in rows]);q=R.from_quat([r['pose'][ref][kind]['q'] for r in rows])
   local=q.inv().apply(h-pos)
   frozen=pos[0]+q[0].apply(local)
   rotations=(q[0].inv()*q).magnitude()*180/np.pi
   m[ref]=dict(local_path=metrics(local),rotation_from_start_max=float(rotations.max()),translation_max=float(np.linalg.norm(pos-pos[0],axis=1).max()),carrier_displacement_max=float(np.linalg.norm(h-frozen,axis=1).max()))
  item[kind]=m
 result.append(item)
print(json.dumps(result,indent=2));(p/'detect_world_arc_metrics.json').write_text(json.dumps(result,indent=2))
