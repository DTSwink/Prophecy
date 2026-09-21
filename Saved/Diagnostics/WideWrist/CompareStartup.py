import pathlib,json,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path(__file__).parent
def rows(mode):return [r for r in json.loads((p/f'native_{mode}.json').read_text())['rows'] if r['actor'].endswith('_C_1')]
a,b=rows('current'),rows('free')
def angle(q1,q2):return np.degrees((R.from_quat(q1).inv()*R.from_quat(q2)).magnitude())
def near(rs,t):return min(rs,key=lambda r:abs(r['t']-t))
for t in (0.5,1,1.3,1.5,1.6,1.616667,1.633333,1.65,1.7,1.8,2,3,4):
    ra,rb=near(a,t),near(b,t)
    print('\nt',ra['t'],rb['t'])
    for bone in ('upperarm_r','lowerarm_r','hand_r'):
        aa,bb=ra['bones'][bone],rb['bones'][bone]
        print(bone,'physical difference',round(angle(aa['q'],bb['q']),5),'target difference',round(angle(aa['target'],bb['target']),5),'errors current/free',round(angle(aa['q'],aa['target']),5),round(angle(bb['q'],bb['target']),5))
print('\nInterval1.3-1.6 beforestop')
for mode,rs in [('limited',a),('free',b)]:
    r1,r2=near(rs,1.3),near(rs,1.6)
    for bone in ('upperarm_r','lowerarm_r','hand_r'):
        print(mode,bone,'physical rotation',angle(r1['bones'][bone]['q'],r2['bones'][bone]['q']),'target rotation',angle(r1['bones'][bone]['target'],r2['bones'][bone]['target']))
