import json,sys
from pathlib import Path
import numpy as np
tag=sys.argv[1] if len(sys.argv)>1 else 'second_pike_inward'
p=Path('Saved/Diagnostics/ArmReach')
d=json.loads((p/(tag+'.json')).read_text());rows=d['rows'];actor=rows[0]['actor']
last=None;ends=[]
for r in rows:
 if r['attack']!=last:
  print('state',r['tick'],r['attack'])
  if r['attack']=='None' and last is not None:ends.append(r['tick'])
  last=r['attack']
records=[];session=-1;prev=1e9
for line in (p/(tag+'.log')).read_text(errors='replace').splitlines():
 if 'SlashSolveAudit,' not in line:continue
 v=line.split('SlashSolveAudit,')[1].split(',')
 if v[0]!=actor or v[1]!='0':continue
 v=np.array(v[2:],float)
 if v[0]<prev:session+=1
 prev=v[0];st=v[3:].reshape(-1,7)
 def pole(s,e,w):
  axis=w[:3]-s[:3];axis/=np.linalg.norm(axis);u=e[:3]-s[:3];v=u-axis*(axis@u);return v/max(1e-9,np.linalg.norm(v))
 raw=pole(*st[:3]);guide=pole(*st[4:7]);final=pole(*st[7:10])
 records.append(dict(session=session,elapsed=float(v[0]),alpha=float(v[2]),st=st.tolist(),raw=raw.tolist(),guide=guide.tolist(),final=final.tolist()))
 if session==1 and round(v[0]*60)%6 in [0,1]:print('second',round(v[0],3),'alpha',round(v[2],3),'raw pole',np.round(raw,2),'guide',np.round(guide,2),'final',np.round(final,2),'elbow Y raw/final',np.round([st[1,1],st[8,1]],2))
(p/(tag+'_stages.json')).write_text(json.dumps(records))
print('sessions',session+1,'end ticks',ends)
