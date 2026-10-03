import json,pathlib,numpy as np,sys
from scipy.spatial.transform import Rotation as R
tag=sys.argv[1] if len(sys.argv)>1 else 'elbow365_before'
d=json.loads((pathlib.Path('Saved/Diagnostics/Knee202')/(tag+'.json')).read_text());rows={r['tick']:r for r in d['rows']}
def pose(t,b,physical=False):return rows[t]['meshes']['PhysicalMesh'][b] if physical else rows[t]['raw'][b]['presented']
def local(t,b):
 p,s=pose(t,b),pose(t,'spine_05');return R.from_quat(s['q']).inv().apply(np.array(p['p'])-s['p'])
def step(t,b):
 a,c=pose(t-1,b),pose(t,b)
 return np.linalg.norm(np.array(c['p'])-a['p']),np.degrees((R.from_quat(c['q'])*R.from_quat(a['q']).inv()).magnitude())
print(tag,d['reason'],len(rows))
for t in range(335,390):
 if t not in rows or t-1 not in rows:continue
 s,e,h=[np.array(pose(t,b)['p']) for b in ['upperarm_l','lowerarm_l','hand_l']]
 a=h-s;a/=max(np.linalg.norm(a),1e-8);rad=np.linalg.norm(e-s-a*np.dot(e-s,a))
 print(t,rows[t]['attack'],'elbowstep',np.round(step(t,'lowerarm_l'),2),'local',np.round(local(t,'lowerarm_l'),2),'localstep',round(np.linalg.norm(local(t,'lowerarm_l')-local(t-1,'lowerarm_l')),2),'radius',round(rad,2),'len',np.round([np.linalg.norm(e-s),np.linalg.norm(h-e)],2),'physErr',round(np.linalg.norm(e-pose(t,'lowerarm_l',True)['p']),2))
