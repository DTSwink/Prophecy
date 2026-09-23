import json,sys,math
import numpy as np
from pathlib import Path
def angle(a,b):
    a=np.asarray(a);b=np.asarray(b)
    return math.degrees(math.acos(float(np.clip(np.dot(a,b)/max(np.linalg.norm(a)*np.linalg.norm(b),1e-12),-1,1))))
def qa(a,b):return math.degrees(2*math.acos(min(1,abs(float(np.dot(a,b))))))
for path in sys.argv[1:]:
    d=json.loads(Path(path).read_text());agents={r['agent'] for r in d['rows']}
    result={'file':path,'frames':d['frames'],'error':d['error'],'agents':{}}
    for agent in sorted(agents):
        rows=[r for r in d['rows'] if r['agent']==agent];events=[];last=None;age=None
        metrics={s:{k:[] for k in ('upper_step','forearm_step','elbow_cm','forearm_length_step')} for s in ('l','r')}
        for row in rows:
            if last and 'ATTACKING' in last['state'] and 'LOCOMOTION' in row['state']:
                age=0;events.append(row['frame'])
            if 'ATTACKING' in row['state']:age=None
            if age is not None:age+=1
            if last and age is not None and age<=90:
                for s in metrics:
                    bones=['upperarm_'+s,'lowerarm_'+s,'hand_'+s]
                    if not all(b in row['bones'] and b in last['bones'] for b in bones):continue
                    now=[np.array(row['bones'][b][1]) for b in bones];old=[np.array(last['bones'][b][1]) for b in bones]
                    m=metrics[s]
                    m['upper_step'].append(qa(now[0][3:],old[0][3:]))
                    m['forearm_step'].append(qa(now[1][3:],old[1][3:]))
                    m['elbow_cm'].append(float(np.linalg.norm((now[1][:3]-now[0][:3])-(old[1][:3]-old[0][:3]))))
                    m['forearm_length_step'].append(abs(float(np.linalg.norm(now[2][:3]-now[1][:3])-np.linalg.norm(old[2][:3]-old[1][:3]))))
            last=row
        if events:
            result['agents'][agent]={'exits':events,'metrics':{s:{k:{'max':max(v),'p95':float(np.percentile(v,95))} for k,v in m.items() if v} for s,m in metrics.items()}}
    print(json.dumps(result,indent=2))
