import json,pathlib,numpy as np
p=pathlib.Path('Saved/Diagnostics');a=json.loads((p/'Pelvis360-baseline-capture.json').read_text())['rows'];b=json.loads((p/'Pelvis360-switch-capture.json').read_text())['rows']
print('maxprefix',max(np.linalg.norm(np.array(x['targets'][n]['target']['p'])-y['targets'][n]['target']['p']) for x,y in zip(a,b) if x['tick']<=366 for n in x['targets']))
for rows,name in ((a,'baseline'),(b,'switch')):
 print(name)
 for i,r in enumerate(rows):
  if i and 365<=r['tick']<=375:
   d=np.array(r['targets']['pelvis']['target']['p'])-rows[i-1]['targets']['pelvis']['target']['p'];print(r['tick'],np.round(d,4),round(np.linalg.norm(d[:2]),4))
