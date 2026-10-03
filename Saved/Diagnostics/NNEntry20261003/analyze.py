import json,sys,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
p=Path(__file__).resolve().parent
mode=sys.argv[1] if len(sys.argv)>1 else 'after'
a={r['tick']:r for r in json.loads((p/(mode+'.json')).read_text())['rows']}
def pose(t,n,k='presented',parent=None):
    v=a[t]['bones'][n][k]
    if v is None:return None
    pos=np.array(v['p']);rot=R.from_quat(v['q'])
    if parent:
        b=a[t]['bones'][parent][k]
        if b is None:return None
        q=R.from_quat(b['q']);pos=q.inv().apply(pos-b['p']);rot=q.inv()*rot
    return pos,rot
def metrics(n,parent,start,end):
    out={}
    for k in ('presented','body'):
        rs={t:pose(t,n,k,parent) for t in range(start-2,end+1)}
        if any(x is None for x in rs.values()):continue
        out[k]={t:{'step_cm':float(np.linalg.norm(rs[t][0]-rs[t-1][0])),
            'velocity_change_cm_per_tick':float(np.linalg.norm(rs[t][0]-2*rs[t-1][0]+rs[t-2][0])),
            'rotation_deg':float(np.degrees((rs[t][1]*rs[t-1][1].inv()).magnitude()))}
            for t in range(start,end+1)}
    return out
out={}
for start,end in ((166,195),(346,375),(500,531)):
    for n,parent in [('head','pelvis'),('hand_l','spine_05'),('hand_r','spine_05'),('hand_l','lowerarm_l'),('hand_r','lowerarm_r')]:
        key=f'{n}_relative_{parent}_{start}'
        out[key]=metrics(n,parent,start,end)
        if parent!='lowerarm_l' and parent!='lowerarm_r':
            print(key)
            for t,m in out[key]['presented'].items():
                print(t,*(round(v,4) for v in m.values()))
(p/(mode+'-motion.json')).write_text(json.dumps(out,indent=2))
print('attack changes',[(t,a[t]['attack']) for t in sorted(a) if t-1 in a and a[t]['attack']!=a[t-1]['attack'] and (a[t]['attack']=='None' or a[t-1]['attack']=='None')])
