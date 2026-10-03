import json,sys,numpy as np
from pathlib import Path
for path in sys.argv[1:]:
    rows=[r for r in json.loads(Path(path).read_text())['rows'] if r['agent'].endswith('_1')]
    changes=[]
    for a,b in zip(rows[1:],rows):
        if 'LOCOMOTION' not in a['state'] or a['frame']<130:continue
        for s in ('l','r'):
            x=np.array(a['bones']['upperarm_'+s][1]);y=np.array(b['bones']['upperarm_'+s][1])
            step=float(np.degrees(2*np.arccos(np.clip(abs(np.dot(x[3:],y[3:])),0,1))))
            changes.append((a['frame'],s,step,a['alpha']))
    print(path,sorted(changes,key=lambda x:x[2],reverse=True)[:12])
    for a in rows:
        if a['frame'] not in (129,130,131,132,133,134,135,136,137,138,139,140):continue
        print(a['frame'],a['alpha'],[[s,[[round(x,3) for x in a['bones'][b+'_'+s][0][:3]] for b in ('upperarm','lowerarm','hand')]] for s in ('l','r')])
