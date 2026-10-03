import json,numpy as np
from scipy.spatial.transform import Rotation as R
p='Saved/Diagnostics/AttackStartInertia-runtime.json'
d=json.load(open(p));rows=d['rows'];print('reason',d['reason'],'rows',len(rows))
first=next(i for i,r in enumerate(rows) if r['triggered'])
print('trigger sample',first,'time',rows[first]['t'])
for i in range(first-2,min(first+10,len(rows))):
 r=rows[i];delta=np.array(r['target']['p'])-rows[i-1]['target']['p'] if i else np.zeros(3)
 err=np.linalg.norm(np.array(r['physical']['p'])-r['target']['p'])
 # Published pose is affine for location in this current-mode capture.
 raw=(1-r['alpha'])*np.array(r['previous']['p'])+r['alpha']*np.array(r['future']['p'])
 print(i-first+1,round(r['t'],5),'delta',np.round(delta,6),'physical error',round(err,7),'offset',round(np.linalg.norm(np.array(r['target']['p'])-raw),7),r['state'])
a=rows[first-2]['target'];b=rows[first-1]['target'];c=rows[first]['target']
print('first delta error',np.linalg.norm((np.array(c['p'])-b['p'])-(np.array(b['p'])-a['p'])))
print('first rotation delta error',np.linalg.norm(((R.from_quat(c['q'])*R.from_quat(b['q']).inv())*(R.from_quat(b['q'])*R.from_quat(a['q']).inv()).inv()).as_rotvec()))
