import json,numpy as np
from scipy.spatial.transform import Rotation as R
from pathlib import Path
p=Path('Saved/Diagnostics/Knee202/fk_exit626.json');d=json.loads(p.read_text(encoding='utf8'));rows=d['rows'];print(d['reason'],len(rows))
for x in rows:
 if 616<=x['tick']<=644:
  h=x['targets']['hand_r'];z=h['target']['p'][2];a=x['attack'];r=x['raw']; dif=[]
  for b,parent in [('upperarm_r','clavicle_r'),('lowerarm_r','upperarm_r'),('hand_r','lowerarm_r')]:
   t=x['targets']; qs=[]
   for k in ['previous','future']:qs.append(R.from_quat(t[parent][k]['q']).inv()*R.from_quat(t[b][k]['q']))
   dif.append(round((qs[0].inv()*qs[1]).magnitude()*180/np.pi,4))
  print(x['tick'],a, 'alpha',round(h['alpha'],3),'hand z',round(z,4),'futureZ',round(h['future']['p'][2],4),'prevZ',round(h['previous']['p'][2],4),'local dq',dif)
