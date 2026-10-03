import json,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
p=Path('Saved/Diagnostics/Knee202');data=json.loads((p/'hand180.json').read_text());rows=data['rows']
print(data['reason'],data['owned'],len(rows),rows[0]['meshes'].keys())
last=None
for r in rows:
 if r['attack']!=last:print('STATE',r['tick'],r['attack']);last=r['attack']
def pos(r,b,kind='target'):return np.array(r['targets'][b][kind]['p'])
def local(r,kind='target'):
 s=r['targets']['spine_05'][kind]
 return R.from_quat(s['q']).inv().apply(pos(r,'hand_r',kind)-s['p'])
for i,r in enumerate(rows):
 if i and 165<=r['tick']<=205:
  prev=rows[i-1];ph=r['meshes']['PhysicalMesh']['hand_r']['p'];pp=prev['meshes']['PhysicalMesh']['hand_r']['p']
  print(r['tick'],r['attack'],'target_step',round(np.linalg.norm(pos(r,'hand_r')-pos(prev,'hand_r')),3),'physical_step',round(np.linalg.norm(np.array(ph)-pp),3),'local_step',round(np.linalg.norm(local(r)-local(prev)),3),'local',np.round(local(r),2),'future_local',np.round(local(r,'future'),2))
