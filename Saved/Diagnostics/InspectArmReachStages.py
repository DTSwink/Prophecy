import json,numpy as np
from pathlib import Path
d=json.loads(Path('Saved/Diagnostics/ArmReach/before.json').read_text());rows=d['rows'];name=rows[0]['actor']
lines=Path('Saved/Diagnostics/ArmReach/before.log').read_text(errors='replace').splitlines()
pending=None;count=0
for l in lines:
 if 'SlashElbowAudit,' in l:
  v=l.split('SlashElbowAudit,')[1].split(',')
  if v[0]==name:pending=v
 elif 'SlashReturnAudit,' in l and pending:
  v=l.split('SlashReturnAudit,')[1].split(',')
  if v[0]!=name:continue
  x=pending;pending=None;arm=count%2;count+=1
  if count>60:break
  if arm:continue
  ns,ne,nh=[np.array(x[i:i+3],float) for i in (31,38,45)]
  actual=np.array(v[24:27],float);final=np.array(v[21:24],float);length=float(v[27])+float(v[28]);ideal=np.linalg.norm(nh-actual)
  print('LEFT',v[1],'shoulder_offset',round(np.linalg.norm(ns-actual),2),'target_reach',round(ideal,2),'chain',round(length,2),'final_reach',round(np.linalg.norm(final-actual),2))
print('FIRST LEFT BEND')
for r in rows:
 if r['tick'] not in range(119,180,2):continue
 p=np.array([r['pose'][n+'_l']['future']['p'] for n in ['upperarm','lowerarm','hand']]);u=p[1]-p[0];v=p[2]-p[1]
 print(r['tick'],round(np.degrees(np.arccos(np.clip(u@v/np.linalg.norm(u)/np.linalg.norm(v),-1,1))),2))
