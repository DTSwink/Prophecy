import json,numpy as np
from scipy.spatial.transform import Rotation as R
from pathlib import Path
p=Path('Saved/Diagnostics/Head24520261003');a={r['tick']:r for r in json.loads((p/'baseline.json').read_text())['rows']}
print('transitions',[(t,a[t]['attack']) for t in a if t-1 in a and a[t]['attack']!=a[t-1]['attack'] and (a[t]['attack']=='None' or a[t-1]['attack']=='None')])
def local(t,b,k,par='pelvis'):
 z=a[t]['bones'][b][k]; v=a[t]['bones'][par][k];q=R.from_quat(v['q']);return q.inv().apply(np.array(z['p'])-v['p']),q.inv()*R.from_quat(z['q'])
print('tick: target head local XYZ, step, rotstep; physical head local XYZ,step,rotstep; pelvis rotstep')
for t in range(208,261):
 vals=[]
 for k in ['presented','body']:
  pos,q=local(t,'head',k);prev,qp=local(t-1,'head',k)
  vals.extend([*(round(x,3) for x in pos),round(np.linalg.norm(pos-prev),3),round(np.degrees((q*qp.inv()).magnitude()),3)])
 pelvis=R.from_quat(a[t]['bones']['pelvis']['presented']['q']);pp=R.from_quat(a[t-1]['bones']['pelvis']['presented']['q'])
 print(t,vals,round(np.degrees((pelvis*pp.inv()).magnitude()),3))
