import json,sys,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation
d=json.loads(Path(sys.argv[1]).read_text());groups={}
for r in d['rows']:groups.setdefault(r['agent'],[]).append(r)
print('error',d['error'],'frames',d['frames'])
for name,rows in groups.items():
    starts=[i for i in range(1,len(rows)) if 'ATTACKING' in rows[i]['state'] and 'ATTACKING' not in rows[i-1]['state']]
    if not starts:continue
    print(name,'starts',[rows[i]['frame'] for i in starts])
    for i in starts:
        print('START',rows[i]['frame'])
        for j in range(max(1,i-4),min(len(rows),i+5)):
            a,b=rows[j-1],rows[j]
            disp={n:np.linalg.norm(np.array(b['bones'][n][1][:3])-a['bones'][n][1][:3]) for n in b['bones']}
            print(j-i,'wall_ms',round(1000*(b['wall']-a['wall']),1),'game_ms',round(1000*(b['time']-a['time']),1),'alpha',round(b['alpha'],2),'head_cm',round(disp['head'],2),'pelvis_cm',round(disp['pelvis'],2),'max',max(disp,key=disp.get),round(max(disp.values()),2))
