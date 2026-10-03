import json,numpy as np
from pathlib import Path
tag='instability260'
rows=json.loads(Path('Saved/Diagnostics/ArmReach/'+tag+'.json').read_text())['rows'];name=rows[0]['actor']
groups=[];group=[];last=100
for line in Path('Saved/Diagnostics/ArmReach/'+tag+'.log').read_text(errors='replace').splitlines():
 if 'SlashReturnAudit,' not in line:continue
 v=line.split('SlashReturnAudit,')[1].split(',')
 if v[0]!=name:continue
 v=np.array(v[1:],float)
 if v[0]<last:
  if group:groups.append(group)
  group=[]
 group.append(v);last=v[0]
if group:groups.append(group)
for g in groups:
 print('GROUP',len(g))
 for v in g[1::2]:
  if .65<v[0]<1.05:print('time',round(v[0],3),'alpha',round(v[3],3),'route',v[5:8].round(2),'neutral',v[8:11].round(2),'nn',v[11:14].round(2),'target',v[14:17].round(2),'finaltorso',v[20:23].round(2))
