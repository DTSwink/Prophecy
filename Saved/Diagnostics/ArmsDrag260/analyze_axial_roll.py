from pathlib import Path
import json,sys,math,re
import numpy as np
from scipy.spatial.transform import Rotation as R
p=Path(__file__).parent
def rows(tag):
 d=json.loads((p/(tag+'.json')).read_text());assert not d['error'],d['error']
 return {r['tick']:r for r in d['rows'] if r['player']}
def between(a,b):
 v=np.cross(a,b);w=1+np.dot(a,b)
 return R.from_quat(np.r_[v,w]/np.linalg.norm(np.r_[v,w]))
def roll(q,target,axis):
 aim=q.apply(axis);goal=between(target.apply(axis),aim)*target
 d=(goal*q.inv()).as_quat()
 if d[3]<0:d=-d
 return math.degrees(2*math.atan2(d[:3]@aim,d[3]))
on=rows(sys.argv[1]);off=rows(sys.argv[2]);out=[]
ref=R.from_quat(list(map(float,re.search(r'WristIdleReference q=([\d.,-]+)',(p/(sys.argv[1]+'.log')).read_text())[1].split(','))))
axis=R.from_quat(on[1]['weapon']['grip']['q']).apply([0,0,1])
for t,a in on.items():
 b=off[t];q=R.from_quat(a['future']['hand_r']['q']);raw=R.from_quat(b['future']['hand_r']['q'])
 root=R.from_quat(a['meshes']['PhysicalMesh']['root']['q']);idle=root*ref
 out.append(dict(tick=t,raw_roll_error=roll(q,raw,axis),idle_roll_error=roll(q,idle,axis),raw_to_idle_roll=roll(raw,idle,axis),position_difference=math.dist(a['future']['hand_r']['p'],b['future']['hand_r']['p'])))
summary=dict(samples=[r for r in out if r['tick'] in (189,191,200,210,220,230,240,250,260,270,281,300,310,311,312)],max_position_difference=max(r['position_difference'] for r in out))
(p/(sys.argv[1]+'_axial.json')).write_text(json.dumps(dict(summary=summary,rows=out),indent=2))
print(json.dumps(summary))
