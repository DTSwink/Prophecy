import json,sys
from pathlib import Path
import numpy as np
p=Path(sys.argv[1]);d=json.loads(p.read_text());previous={};start={};worst={};attacks={}
for row in d['rows']:
    who=row['agent'];old=previous.get(who);previous[who]=row
    if 'ATTACKING' in row['state']:attacks[who]=row['attack'];continue
    if old and 'ATTACKING' in old['state']:start[who]=row['frame']
    if who not in start:continue
    b=row['bones'];pos=lambda name:np.array(b[name][0][:3])
    up=pos('neck_01')-pos('pelvis');up/=np.linalg.norm(up)
    right=pos('upperarm_r')-pos('upperarm_l');width=np.linalg.norm(right);right-=up*np.dot(right,up);right/=np.linalg.norm(right)
    forward=np.cross(right,up);m=np.stack([forward,right,up]);origin=(pos('upperarm_l')+pos('upperarm_r'))*.5
    hand=m@(pos('hand_r')-origin);elbow=m@(pos('lowerarm_r')-origin)
    key=(who,start[who]);v=worst.setdefault(key,{'attack':attacks.get(who),'points':[]})
    if row['frame']-start[who]<35:v['points'].append([row['frame']-start[who],*np.round(hand,2),*np.round(elbow,2),round(width,2)])
print(json.dumps([{'agent':k[0],'start':k[1],**v} for k,v in worst.items()],indent=2))
