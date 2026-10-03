import json,sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
d=json.loads(Path(sys.argv[1]).read_text());old={};exits={};out={}
def frame(row,slot):
    b=row['bones'];v=lambda n:np.array(b[n][slot][:3])
    up=v('neck_01')-v('pelvis');up/=np.linalg.norm(up)
    right=v('upperarm_r')-v('upperarm_l');width=np.linalg.norm(right)/2
    right-=up*np.dot(right,up);right/=np.linalg.norm(right)
    m=np.stack([np.cross(right,up),right,up]);o=(v('upperarm_l')+v('upperarm_r'))/2
    return m,o,width
for r in d['rows']:
    a=r['agent'];prev=old.get(a);old[a]=r
    if prev and 'ATTACKING' in prev['state'] and 'LOCOMOTION' in r['state']:exits[a]=r['frame']
    if a not in exits or 'LOCOMOTION' not in r['state']:continue
    key=f"{a}:{exits[a]}";z=out.setdefault(key,{'frames':0,'wrist_front_min_in_body_width':1000,'forearm_ellipse_min':1000,'upperarm_ellipse_min':1000,'wrist_step_max':0,'forearm_rotation_step_max':0,'path':[]})
    m,o,w=frame(r,0);hand=m@(np.array(r['bones']['hand_r'][0][:3])-o);elbow=m@(np.array(r['bones']['lowerarm_r'][0][:3])-o)
    z['frames']+=1
    if abs(hand[1])<w:z['wrist_front_min_in_body_width']=min(z['wrist_front_min_in_body_width'],float(hand[0]))
    for t in np.linspace(0,1,101):
        p=elbow+(hand-elbow)*t
        # Torso core only, excluding the shoulder attachment surface and low hands.
        if -40<p[2]<0:z['forearm_ellipse_min']=min(z['forearm_ellipse_min'],float((p[0]/(w*.7))**2+(p[1]/(w*.65))**2))
        shoulder=m@(np.array(r['bones']['upperarm_r'][0][:3])-o)
        p=shoulder+(elbow-shoulder)*t
        if -40<p[2]<0:z['upperarm_ellipse_min']=min(z['upperarm_ellipse_min'],float((p[0]/(w*.7))**2+(p[1]/(w*.65))**2))
    if prev and 'LOCOMOTION' in prev['state']:
        pm,po,pw=frame(prev,0);ph=pm@(np.array(prev['bones']['hand_r'][0][:3])-po)
        z['wrist_step_max']=max(z['wrist_step_max'],float(np.linalg.norm(hand-ph)))
        q=Rotation.from_quat(r['bones']['lowerarm_r'][0][3:]);pq=Rotation.from_quat(prev['bones']['lowerarm_r'][0][3:])
        z['forearm_rotation_step_max']=max(z['forearm_rotation_step_max'],float((pq.inv()*q).magnitude()*180/np.pi))
    if (r['frame']-exits[a])%8==0:z['path'].append([r['frame']-exits[a],*np.round(hand,2)])
print(json.dumps(out,indent=1))
Path(sys.argv[1]).with_suffix('.metrics.json').write_text(json.dumps(out,indent=2))
