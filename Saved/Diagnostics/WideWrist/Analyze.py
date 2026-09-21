import json,pathlib,sys,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path(__file__).resolve().parent
d=json.loads((p/(sys.argv[1]+'.json')).read_text())
print(d['reason'],len(d['rows']))
for actor in sorted({r['actor'] for r in d['rows']}):
    rows=[r for r in d['rows'] if r['actor']==actor and r['t']>=5]
    print(actor,'controller',rows[0]['player'],'limits',rows[0]['limits'], 'limit_variants',len({str(r['limits']) for r in rows}))
    for bone,parent in [('lowerarm_r','upperarm_r'),('hand_r','lowerarm_r'),('lowerarm_l','upperarm_l'),('hand_l','lowerarm_l')]:
        q=np.array([r['bones'][bone]['q'] for r in rows]);par=np.array([r['bones'][parent]['q'] for r in rows])
        target=np.array([r['bones'][bone]['target'] for r in rows]); w=np.array([r['bones'][bone]['w'] for r in rows])
        rel=(R.from_quat(par).inv()*R.from_quat(q)).as_quat()
        twist=np.unwrap(2*np.arctan2(rel[:,0],rel[:,3]));twist=np.degrees(twist)
        err=np.degrees((R.from_quat(q).inv()*R.from_quat(target)).magnitude())
        step=np.degrees((R.from_quat(q[:-1]).inv()*R.from_quat(q[1:])).magnitude())
        print(bone,'speed_p50/max',np.round(np.percentile(np.linalg.norm(w,axis=1),[50,100]),2),'step_max',round(step.max(),2),
           'error_p50/max',np.round(np.percentile(err,[50,100]),2),'parent_frame_twist_span',round(np.ptp(twist),2))
