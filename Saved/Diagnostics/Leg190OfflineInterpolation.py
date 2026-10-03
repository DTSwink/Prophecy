import json,pathlib,numpy as np
from ReplayTemperedLeg import rot,unit
p=pathlib.Path('Saved/Diagnostics');r=json.loads((p/'Leg190-live.json').read_text())['rows'];f={round(x['time']*60):x for x in map(json.loads,(p/'Leg190-frozen.jsonl').read_text().splitlines()) if x['offset']==25}
for x in r:
 t=x['tick']
 if not 187<=t<=201:continue
 tr=f[t if t%2 else t-1];length=[]
 for n in ('previous','after'):
  s=np.array(tr[n]);h=s[:3]+np.array(tr['hip'])@rot(s,3);k=h+np.array(tr['knee'])@rot(s,34);length.append(np.linalg.norm(s[25:28]-k)*100)
 a=.5 if t%2 else 1.;L=length[0]*(1-a)+length[1]*a
 b=x['targets'];h,k,e=[np.array(b[n+'_r']['p']) for n in ('thigh','calf','foot')];U=np.linalg.norm(k-h);D=np.linalg.norm(e-h)
 cos=(D*D-U*U-L*L)/(2*U*L);angle=np.degrees(np.arccos(np.clip(cos,-1,1)))
 old=np.degrees(np.arccos(np.clip(unit(k-h)@unit(e-k),-1,1)))
 print(t,round(old,2),round(angle,2),round(L,3))
