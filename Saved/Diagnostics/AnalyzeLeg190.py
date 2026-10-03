import pathlib,json,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics');rows=json.loads((p/'Leg190-live.json').read_text())['rows']
def unit(v):return v/max(np.linalg.norm(v),1e-10)
def metrics(b,s):
 h,k,f=[np.array(b[n+'_'+s]['p']) for n in ('thigh','calf','foot')];a=unit(f-h);rad=k-h-a*np.dot(k-h,a)
 return np.degrees(np.arccos(np.clip(unit(k-h)@unit(f-k),-1,1))),R.from_quat(b['foot_'+s]['q']).inv().apply(unit(rad)),np.linalg.norm(f-k)
for i,x in enumerate(rows):
 if i and x['attack']!=rows[i-1]['attack'] and (x['attack']=='None' or rows[i-1]['attack']=='None'):print('transition',x['tick'],rows[i-1]['attack'],x['attack'])
print('meshes',list(rows[180]['meshes']))
for i,x in enumerate(rows):
 if not 178<=x['tick']<=206:continue
 b=x['targets'];old=rows[i-1]['targets'];out=[]
 for s in ('l','r'):
  bend,pole,length=metrics(b,s);_,op,_=metrics(old,s)
  out.extend([round(bend,2),round(np.degrees(np.arccos(np.clip(op@pole,-1,1))),2),round(length,3),round(np.linalg.norm(np.array(b['foot_'+s]['p'])-old['foot_'+s]['p']),3)])
 print(x['tick'],out)
tr=[json.loads(l) for l in (p/'Leg190-frozen.jsonl').read_text().splitlines()]
print('trace',[(round(x['time']*60),x['offset'],round(x['max_turn']*180/np.pi,3)) for x in tr if 176<round(x['time']*60)<207])
