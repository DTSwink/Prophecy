import json, math, sys, pathlib
import numpy as np
from scipy.spatial.transform import Rotation as R
folder=pathlib.Path(__file__).resolve().parent
source=folder/(sys.argv[1]+'.json')
d=json.loads(source.read_text())
print('Capture',source.name,d['reason'],'rows',len(d['rows']))
def angle(a,b):
    return math.degrees(2*math.acos(min(1.,abs(float(np.dot(a,b)))/(np.linalg.norm(a)*np.linalg.norm(b)))))
for name in sorted({x['actor'] for x in d['rows']}):
    rows=[x for x in d['rows'] if x['actor']==name]
    events=[]
    for a,b in zip(rows,rows[1:]):
        if b['t']<5: continue
        x,y=a['bones']['hand_l'],b['bones']['hand_l']
        fore0,fore1=a['bones']['lowerarm_l'],b['bones']['lowerarm_l']
        rel0=(R.from_quat(fore0['q']).inv()*R.from_quat(x['q'])).as_quat()
        rel1=(R.from_quat(fore1['q']).inv()*R.from_quat(y['q'])).as_quat()
        events.append(dict(t=round(b['t'],5),dt=round(b['t']-a['t'],5),wall_dt=round(b['wall']-a['wall'],4),
            step=angle(x['q'],y['q']),relative_step=angle(rel0,rel1),target_step=angle(x['target'],y['target']),
            future_step=angle(x['future'],y['future']),parent_step=angle(fore0['q'],fore1['q']),
            error=angle(y['q'],y['target']),speed=np.linalg.norm(y['w']),visible_step=angle(x['visible'],y['visible']),
            limits_changed=a['limits']!=b['limits']))
    print('\n',name,'duration',rows[-1]['t']-rows[0]['t'],'limits',sorted({x['limits'] for x in rows})[:1])
    for key in ('step','relative_step','target_step','parent_step','speed'):
        vals=np.array([e[key] for e in events]);print(key,'p50/p95/p99/max',np.round(np.percentile(vals,[50,95,99,100]),3))
    print('Largest steps:',json.dumps(sorted(events,key=lambda e:e['step'],reverse=True)[:10],indent=2))
    (folder/(source.stem+'_'+name+'_events.json')).write_text(json.dumps(events))
