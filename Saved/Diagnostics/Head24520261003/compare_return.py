import json,numpy as np
from scipy.spatial.transform import Rotation as R
from pathlib import Path
p=Path('Saved/Diagnostics/Head24520261003')
def load(m):return {r['tick']:r for r in json.loads((p/(m+'.json')).read_text())['rows']}
a=load('baseline');b=load('return_off')
print('prefix max error',max(np.linalg.norm(np.array(a[t]['bones']['head']['presented']['p'])-b[t]['bones']['head']['presented']['p']) for t in a if t<=211))
def head(t,rs):
 x=rs[t]['bones'];q=R.from_quat(x['pelvis']['presented']['q']);return q.inv().apply(np.array(x['head']['presented']['p'])-x['pelvis']['presented']['p'])
def angle(t,rs,bone='head',par='neck_02'):
 def rot(t):
  x=rs[t]['bones'];return R.from_quat(x[par]['presented']['q']).inv()*R.from_quat(x[bone]['presented']['q'])
 return np.degrees((rot(t)*rot(t-1).inv()).magnitude())
for t in range(213,271,2):
 print(t,'baseline',round(np.linalg.norm(head(t,a)-head(t-1,a)),3),round(angle(t,a),3),'off',round(np.linalg.norm(head(t,b)-head(t-1,b)),3),round(angle(t,b),3))
