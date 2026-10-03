import json,numpy as np
from pathlib import Path
import sys
tag=sys.argv[1] if len(sys.argv)>1 else 'variants'
name=json.loads(Path('Saved/Diagnostics/ArmReach/'+tag+'.json').read_text())['rows'][0]['actor']
seq=-1;last=1e9;arm=0
for l in Path('Saved/Diagnostics/ArmReach/'+tag+'.log').read_text(errors='replace').splitlines():
 if 'SlashReturnAudit,' not in l:continue
 v=l.split('SlashReturnAudit,')[1].split(',')
 if v[0]!=name:continue
 r=np.array(v[1:],float)
 if r[0]<last:seq+=1
 last=r[0]
 if seq==4 and arm%2==1:print(round(r[0],3),'alpha',round(r[3],2),'preclear',r[14:17].round(2),'afterclear',r[17:20].round(2),'solved',r[20:23].round(2),'shoulder',r[23:26].round(2),'lengths',r[26:28].round(2))
 arm+=1
