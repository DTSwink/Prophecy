import json,sys,re
from pathlib import Path
import numpy as np
results=[]
for path in sys.argv[1:]:
    data=json.loads(Path(path).read_text());groups={}
    for row in data['rows']:groups.setdefault(row['agent'],[]).append(row)
    returns=[]
    for agent,rows in groups.items():
        for i in range(3,len(rows)-40):
            if 'ATTACKING' not in rows[i-1]['state'] or 'LOCOMOTION' not in rows[i]['state']:continue
            p=np.array([r['bones']['head'][1][:3] for r in rows]);v=np.diff(p,axis=0)*60;dv=np.linalg.norm(np.diff(v,axis=0),axis=1)
            physical=np.array([r['physical']['head'][:3] for r in rows]);pdv=np.linalg.norm(np.diff(physical,n=2,axis=0)*60,axis=1)
            returns.append({'frame':rows[i]['frame'],'initial_dv':dv[i-1], 'next_dv':dv[i],
                'max_first_10':max(dv[i-1:i+9]),'max_later_10_40':max(dv[i+9:i+39]),
                'max_around_retirement':max(dv[i+26:i+34]), 'physical_max_first_10':max(pdv[i-1:i+9]),
                'physical_max_around_retirement':max(pdv[i+26:i+34]), 'pre_speed':np.linalg.norm(v[i-1]),'first_speed':np.linalg.norm(v[i])})
    result={'file':path,'error':data['error'],'frames':data['frames'],'returns':returns}
    results.append(result)
    print(Path(path).name,len(returns))
    for k in ['initial_dv','next_dv','max_first_10','max_later_10_40','max_around_retirement','physical_max_first_10','physical_max_around_retirement','pre_speed','first_speed']:
        a=[r[k] for r in returns];print(k,round(min(a),3),round(max(a),3))
Path('Saved/Diagnostics/UpperInertiaComparison.json').write_text(json.dumps(results,indent=2))
