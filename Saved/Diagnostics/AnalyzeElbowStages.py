import json,sys,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
def unit(v):return v/max(1e-12,np.linalg.norm(v))
def pole(s,e,h):
 a=unit(h-s);return unit(e-s-a*np.dot(e-s,a))
def transport(p,old,new):
 c=np.dot(old,new)
 return unit(p-(old+new)*np.dot(p,new)/max(1e-9,1+c)) if c>-.999999 else -p
rows=[]
with open('Saved/Logs/GameAnimationSample3.log',encoding='utf-8') as f:
 for line in f:
  if 'SlashElbowAudit,' not in line:continue
  parts=line.split('SlashElbowAudit,')[1].strip().split(',')
  if len(parts)!=58:continue
  x=np.array([float(v) for v in parts[1:]])
  prev=x[9:30].reshape(3,7);neutral=x[30:51].reshape(3,7);e=x[51:54];h=x[54:57];s=neutral[0,:3]
  ax=unit(h-s);po=pole(s,e,h);prior=transport(pole(*prev[:,:3]),unit(prev[2,:3]-prev[0,:3]),ax);goal=transport(pole(*neutral[:,:3]),unit(neutral[2,:3]-neutral[0,:3]),ax)
  angle=lambda a,b:float(np.degrees(np.arccos(np.clip(np.dot(a,b),-1,1))))
  rows.append({'agent':parts[0],'time':x[0],'alpha':x[1],'turn':x[2],'previous':prev.tolist(),'neutral':neutral.tolist(),'localUpper':x[3:6].tolist(),'localPole':x[6:9].tolist(),'e':e.tolist(),'h':h.tolist(),'pole':po.tolist(),'goal':goal.tolist(),'error':angle(po,goal),'step':angle(po,prior)})
out=Path('Saved/Diagnostics/ElbowStages.json');out.write_text(json.dumps(rows,indent=2))
print('rows',len(rows))
for v in rows[-180::5]:print({k:np.round(v[k],3).tolist() if isinstance(v[k],list) else round(v[k],3) if isinstance(v[k],float) else v[k] for k in ('agent','time','alpha','turn','pole','goal','error','step')})
if rows:print('neutral sample',rows[-1]['neutral'])
