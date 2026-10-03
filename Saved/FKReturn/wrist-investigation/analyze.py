import json,re
import numpy as np
from scipy.spatial.transform import Rotation as R
from pathlib import Path
root=Path(__file__).parent
d=json.loads((root/'capture.json').read_text());rows=d['rows'];names=rows[0]['names']
def local(row,bone,parent,kind='future'):
    q=R.from_quat(np.array(row[kind])[:,:4]);return q[names.index(parent)].inv()*q[names.index(bone)]
def angle(a,b):return np.degrees((a.inv()*b).magnitude())
idle={}
for n,q in re.findall(r'TEXT\("(\w+)"\), TEXT\("\w+"\), \d+, \{([^}]+)\}',Path('Source/GameAnimationSample3/Private/ProphecyFKReturnData.h').read_text()):
    idle[n]=R.from_quat([float(x.strip().rstrip('f')) for x in q.split(',')])
print('tick frame future-wrist-twist presented-wrist-twist wrist-idle-gap forearm-idle-gap presented-wrist-step future-wrist-step')
pr=pf=None
for row in rows:
    if row['tick']<123:continue
    f=local(row,'hand_r','lowerarm_r');p=local(row,'hand_r','lowerarm_r','presented');l=local(row,'lowerarm_r','upperarm_r')
    def twist(q):
        v=q.as_quat();return ((np.degrees(2*np.arctan2(v[0],v[3]))+180)%360)-180
    print(row['tick'],row['frame'],*(round(v,2) for v in [twist(f),twist(p),angle(f,idle['hand_r']),angle(l,idle['lowerarm_r']),angle(pr,p) if pr else 0,angle(pf,f) if pf else 0]))
    pr,pf=p,f
