import json,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
p=Path('Saved/Diagnostics/Knee202')
for tag in ['hand180','hand180_no_clamps']:
 rr={r['tick']:r for r in json.loads((p/(tag+'.json')).read_text())['rows']}
 def tr(t,b):return rr[t]['raw'][b]['future']
 print(tag)
 parents={'spine_01':'pelvis','spine_02':'spine_01','spine_03':'spine_02','spine_04':'spine_03','spine_05':'spine_04','clavicle_r':'spine_05','upperarm_r':'clavicle_r','lowerarm_r':'upperarm_r','hand_r':'lowerarm_r'}
 for b,parent in parents.items():
  a,c=tr(190,b),tr(192,b);ap,cp=tr(190,parent),tr(192,parent)
  av=R.from_quat(ap['q']).inv().apply(np.array(a['p'])-ap['p']);cv=R.from_quat(cp['q']).inv().apply(np.array(c['p'])-cp['p'])
  ar=R.from_quat(ap['q']).inv()*R.from_quat(a['q']);cr=R.from_quat(cp['q']).inv()*R.from_quat(c['q'])
  print(b,'local offset delta cm',np.round(cv-av,5),'rotation delta deg',np.degrees((ar.inv()*cr).magnitude()),'lengths',np.linalg.norm(av),np.linalg.norm(cv))
