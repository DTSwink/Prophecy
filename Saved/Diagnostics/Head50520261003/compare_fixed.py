import json,sys,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
p=Path(__file__).resolve().parent
def rows(name):return {r['tick']:r for r in json.loads((p/(name+'.json')).read_text())['rows']}
mode=sys.argv[1] if len(sys.argv)>1 else 'fixed'
a,b=rows('baseline'),rows(mode)
trace=[json.loads(l) for l in (p/'baseline-nn.jsonl').read_text().splitlines()]
out={}
for start,end in ((165,176),(500,512)):
    entry=169 if start==165 else 504
    t=min((t for t in trace if t['actor'].endswith('_0') and t['frame']==2),key=lambda t:abs(t['time']-a[entry+2]['time']))
    axis=R.from_quat(t['anchor'][3:]).as_matrix()[:,0]
    case={}
    for name,rs in [('before',a),('after',b)]:
        case[name]={}
        for kind in ('presented','body'):
            values={i:float(axis@(np.array(rs[i]['bones']['head'][kind]['p'])-rs[i]['bones']['pelvis'][kind]['p'])) for i in range(start,end+1)}
            case[name][kind]={'lateral_cm':values,'steps_cm':{i:values[i]-values[i-1] for i in range(start+1,end+1)}}
    out[str(entry)]=case
out['max_body_difference_before_first_entry_cm']=max(float(np.linalg.norm(np.array(a[t]['bones'][n]['body']['p'])-b[t]['bones'][n]['body']['p'])) for t in a if t<169 for n in a[t]['bones'] if a[t]['bones'][n]['body'])
(p/(mode+'-comparison.json')).write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
