import json,sys,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
d=json.loads(Path(sys.argv[1]).read_text());groups={};out=[]
for row in d['rows']:groups.setdefault(row['agent'],[]).append(row)
for agent,rows in groups.items():
    for i in range(3,len(rows)-16):
        if 'ATTACKING' not in rows[i-1]['state'] or 'LOCOMOTION' not in rows[i]['state']:continue
        samples=[]
        for j in range(i-6,i+17):
            if j<2:continue
            r,p,pp=rows[j],rows[j-1],rows[j-2]
            def pos(row,bone,slot=1):return np.array(row['bones'][bone][slot][:3])
            h=pos(r,'head');v=(h-pos(p,'head'))*60;pv=(pos(p,'head')-pos(pp,'head'))*60
            pelvis_v=(pos(r,'pelvis')-pos(p,'pelvis'))*60
            a=np.linalg.norm(v-pv)*60
            q=R.from_quat(r['bones']['head'][1][3:]);pq=R.from_quat(p['bones']['head'][1][3:])
            samples.append({'tick':j-i,'head':h.tolist(),'head_v':v.tolist(),'speed':float(np.linalg.norm(v)),'velocity_change':float(np.linalg.norm(v-pv)), 'pelvis_speed':float(np.linalg.norm(pelvis_v)),'relative_speed':float(np.linalg.norm(v-pelvis_v)), 'head_rotation_step':float(np.rad2deg((pq.inv()*q).magnitude()))})
        out.append({'agent':agent,'exit':rows[i]['frame'],'attack':rows[i-1]['attack'],'samples':samples})
Path(sys.argv[1]).with_suffix('.head.json').write_text(json.dumps(out,indent=2))
for e in out:
    print(e['agent'],e['exit'],e['attack'])
    for s in e['samples']:
        if -3<=s['tick']<=8:print(s['tick'],*[round(s[k],2) for k in ['speed','velocity_change','pelvis_speed','relative_speed','head_rotation_step']])
