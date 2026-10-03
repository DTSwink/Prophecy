import json,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
p=Path(__file__).resolve().parent
a={r['tick']:r for r in json.loads((p/'synchronized.json').read_text())['rows']}
l=json.loads((p.parents[2]/'Content/locomotion/NN/prophecy_upper_body_runtime.json').read_text())
names=['pelvis','spine_01','spine_02','spine_03','spine_04','spine_05','neck_01','neck_02','head']
def tf(t,n,k):
    v=a[t]['bones'][n][k]
    return (np.array(v['p']),R.from_quat(v['q'])) if v else None
def local(b,parent):return parent[1].inv().apply(b[0]-parent[0]),parent[1].inv()*b[1]
def compose(b,parent):return parent[0]+parent[1].apply(b[0]),parent[1]*b[1]
trace=[json.loads(t) for t in (p/'synchronized-nn.jsonl').read_text().splitlines()]
for t,u in [(169,170),(504,506)]:
    tr=min((r for r in trace if r['actor'].endswith('_0') and r['frame']==2),key=lambda r:abs(r['time']-a[u]['time']))
    axis=R.from_quat(tr['anchor'][3:]).as_matrix()[:,0]
    body={};presented={};future={};rebuilt={};reconstruct={}
    for i,n in enumerate(names):
        presented[n]=tf(t,n,'presented');future[n]=tf(u,n,'presented')
        body[n]=tf(t,n,'body')
        if body[n] is None:body[n]=compose(local(presented[n],presented[names[i-1]]),body[names[i-1]])
        if i==0:rebuilt[n]=reconstruct[n]=future[n];continue
        parent=names[i-1]
        pos,rot=local(future[n],future[parent])
        physpos,physrot=local(body[n],body[parent])
        rebuilt[n]=compose((physpos,rot),rebuilt[parent])
        reconstruct[n]=compose((pos,rot),reconstruct[parent])
    lateral=lambda b:float(axis@(b['head'][0]-b['pelvis'][0]))
    print('entry',t,'startbody',lateral(body),'starttarget',lateral(presented),'nexttarget',lateral(future),
          'physical_offsets_next',lateral(rebuilt),'reconstruct_error',np.linalg.norm(reconstruct['head'][0]-future['head'][0]))
    print('physical offset difference contribution',lateral(future)-lateral(rebuilt))
    print('head expected relative displacement from physical linear velocity',float(axis@(np.array(a[t]['bones']['head']['linear_velocity'])-a[t]['bones']['pelvis']['linear_velocity']))*(u-t)/60)
