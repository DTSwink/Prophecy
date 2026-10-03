import json,math,re
from pathlib import Path
import numpy as np
p=Path(__file__).parent
rows=json.loads((p/'wrap_slashL_before_route.json').read_text())
log=(p/'wrap_slashL_before.log').read_text()
samples=re.findall(r'WristSplit time=(\S+) weight=(\S+) yaw=(\S+) elevation=(\S+)',log)
unwrap=lambda a,near:near+(a-near+180)%360-180
for transport in (False,True):
 for strength in (75,300):
  angle=velocity=body=None
  results=[]
  for time,weight,yaw,elev in samples:
   r=min(rows,key=lambda r:abs(r['time']-float(time)))
   root=r['yaw']-float(yaw)
   inward=r['inward']-root
   if body is None:
    angle=float(yaw);body=unwrap(inward,angle-180)
   else:
    nextbody=unwrap(inward,body)
    if transport: angle+=nextbody-body
    body=nextbody
   goal=unwrap(float(yaw),body+180)
   error=goal-angle;dt=1/30
   velocity=(velocity+strength*error*dt)/(1+max(20,2*math.sqrt(strength))*dt+strength*dt*dt) if velocity is not None else 0
   angle+=np.clip(velocity*dt,min(0,error),max(0,error))
   results.append((r['tick'],round(angle,1),round(body,1),round(goal,1),round(unwrap(angle-body,180),1)))
  print('transport',transport,'strength',strength,results[:15],results[-1])
