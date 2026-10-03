import json,numpy as np
from pathlib import Path
for tag in ['before','target','direct']:
 d=json.loads(Path('Saved/Diagnostics/ArmReach/'+tag+'.json').read_text());name=d['rows'][0]['actor']
 rows=[]
 for l in Path('Saved/Diagnostics/ArmReach/'+tag+'.log').read_text(errors='replace').splitlines():
  if 'SlashReturnAudit,' not in l:continue
  v=l.split('SlashReturnAudit,')[1].split(',')
  if v[0]==name:rows.append(np.array(v[1:],float))
 rows=rows[:60]
 print(tag)
 for arm in [0,1]:
  rs=np.array(rows[arm::2]);print('ARM',arm,'neutralward route y',round(rs[:,6].min(),2),round(rs[:,6].max(),2),'NN blend pre-clear y',round(rs[:,15].min(),2),round(rs[:,15].max(),2),'final torso y',round(rs[:,21].min(),2),round(rs[:,21].max(),2))
  if arm:
   for i in [0,1,3,5,10,15,20,25,29]:
    r=rs[i];print(round(r[0],3),'route',r[5:8].round(1),'idle',r[8:11].round(1),'NN',r[11:14].round(1),'preclear',r[14:17].round(1),'final torso',r[20:23].round(1))
