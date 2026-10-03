import json,numpy as np
from scipy.spatial.transform import Rotation as R
from pathlib import Path
p=Path(__file__).resolve().parent
modes=['baseline','fixed'];data={m:{r['tick']:r for r in json.loads((p/(m+'.json')).read_text())['rows']} for m in modes}
result={}
for mode,a in data.items():
 headings={}
 for t in range(208,241):
  c=np.array([x['p'] for x in a[t]['continuous']]);v=c[-1]-c[0];headings[t]=float(np.degrees(np.arctan2(v[1],v[0])))
 differences=np.diff(list(headings.values()));reversals=sum(differences[i]*differences[i-1]<0 for i in range(1,len(differences)))
 result[mode]={'far_headings':headings,'direction_reversals_208_240':int(reversals)}
 print(mode,'reversals',reversals)
 for t in range(216,225):print(t,round(headings[t],4))
result['root_max_difference_cm']=max(float(np.linalg.norm(np.array(r['root'])-data['fixed'][t]['root'])) for t,r in data['baseline'].items() if t in data['fixed'])
print('root max difference',result['root_max_difference_cm'])
(p/'comparison.json').write_text(json.dumps(result,indent=2))
