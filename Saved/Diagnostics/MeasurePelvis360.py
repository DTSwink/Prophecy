import json,pathlib,numpy as np
r=json.loads(pathlib.Path('Saved/Diagnostics/PunchPole-enabled-live.json').read_text())['rows']
for i,x in enumerate(r):
 if i and 345<=x['tick']<=375:
  d=np.array(x['targets']['pelvis']['p'])-r[i-1]['targets']['pelvis']['p'];print(x['tick'],x['attack'],np.round(d,3),round(float(np.linalg.norm(d[:2])),3))
print('exits',[(x['tick'],r[i-1]['attack']) for i,x in enumerate(r) if i and x['attack']=='None' and r[i-1]['attack']!='None'])
