import pathlib,json,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics')
a=json.loads((p/'Pelvis360V2-baseline-capture.json').read_text())['rows'];b=json.loads((p/'Pelvis360V2-length-capture.json').read_text())['rows']
for tick in (367,368):
 x=next(r for r in a if r['tick']==tick);y=next(r for r in b if r['tick']==tick)
 for n in ('pelvis','foot_l','foot_r'):
  v=x['targets'][n]['target'];w=y['targets'][n]['target'];print('fixed',tick,n,'pos',np.linalg.norm(np.array(v['p'])-w['p']),'rot',np.degrees((R.from_quat(v['q']).inv()*R.from_quat(w['q'])).magnitude()))
summary=[]
for name in ('kicks-old','kicks-new'):
 rows=json.loads((p/('LegRecovery-'+name+'-live.json')).read_text())['rows'];events=[]
 for i,r in enumerate(rows):
  if not i or r['attack']!='None' or rows[i-1]['attack']=='None':continue
  ev=dict(tick=r['tick'],attack=rows[i-1]['attack'])
  for side in ('l','r'):
   steps=[];pelvis=[]
   for j in range(i,min(i+24,len(rows))):
    old=rows[j-1]['targets'];cur=rows[j]['targets'];n='thigh_'+side
    steps.append(float(np.degrees((R.from_quat(old[n]['q']).inv()*R.from_quat(cur[n]['q'])).magnitude())))
    if j>1:
     positions=[np.array(rows[k]['targets']['pelvis']['p']) for k in (j-2,j-1,j)];pelvis.append(float(np.linalg.norm(positions[2]-2*positions[1]+positions[0])))
   ev[side]=dict(thigh_peak=max(steps),pelvis_second_difference=max(pelvis))
  events.append(ev)
 summary.append(dict(mode=name,events=events))
print(json.dumps(summary,indent=2));(p/'LegRecovery-kick-regression.json').write_text(json.dumps(summary,indent=2))
