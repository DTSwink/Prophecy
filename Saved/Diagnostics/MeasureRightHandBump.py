import json,sys,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
data=json.loads(Path(sys.argv[1]).read_text());groups={};result=[]
for row in data['rows']:groups.setdefault(row['agent'],[]).append(row)
for agent,rows in groups.items():
    exits=[i for i in range(1,len(rows)) if 'ATTACKING' in rows[i-1]['state'] and 'LOCOMOTION' in rows[i]['state']]
    for ei,i in enumerate(exits):
        samples=[]
        for j in range(max(2,i-2),min(len(rows),i+70)):
            if j>i and 'ATTACKING' in rows[j]['state']:break
            def pos(k,n,slot=1):return np.array(rows[k]['bones'][n][slot][:3])
            def local(k):
                spine=rows[k]['bones']['spine_05'][1]
                return R.from_quat(spine[3:]).inv().apply(pos(k,'hand_r')-spine[:3])
            v=(pos(j,'hand_r')-pos(j-1,'hand_r'))*60
            lv=(local(j)-local(j-1))*60
            pv=(np.array(rows[j]['physical']['hand_r'][:3])-rows[j-1]['physical']['hand_r'][:3])*60 if 'physical' in rows[j] else v
            samples.append({'tick':j-i,'frame':rows[j]['frame'],'speed':float(np.linalg.norm(v)),'local_speed':float(np.linalg.norm(lv)),'physical_speed':float(np.linalg.norm(pv)),'local':local(j).tolist(),'velocity':v.tolist()})
        result.append({'agent':agent,'exit':rows[i]['frame'],'samples':samples})
        if ei<2:
            print('EXIT',rows[i]['frame'])
            for s in samples:
                if s['tick']%2==0:print(s['tick'],round(s['speed'],1),round(s['local_speed'],1),round(s['physical_speed'],1),[round(x,1) for x in s['local']])
Path(sys.argv[1]).with_suffix('.hand-speed.json').write_text(json.dumps(result,indent=2))
