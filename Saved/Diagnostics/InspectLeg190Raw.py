import json,pathlib,numpy as np
from ReplayTemperedLeg import rot,unit
r=[json.loads(x) for x in pathlib.Path('Saved/Diagnostics/Leg190-frozen.jsonl').read_text().splitlines()]
for x in r:
 t=round(x['time']*60)
 if x['offset']!=25 or not 185<=t<=203:continue
 out=[]
 for label in ('previous','before','after'):
  s=np.array(x[label]);h=s[:3]+np.array(x['hip'])@rot(s,3);k=h+np.array(x['knee'])@rot(s,34);f=s[25:28];out +=[label,round(np.degrees(np.arccos(np.clip(unit(k-h)@unit(f-k),-1,1))),2),round(np.linalg.norm(f-k)*100,3)]
 print(t,out)
