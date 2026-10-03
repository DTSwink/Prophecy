import json,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
exec(Path('Saved/Diagnostics/AnalyzePikeReturn.py').read_text().split("a,b=load('legacy')")[0])
d={r['tick']:r for r in json.loads(Path('Saved/Diagnostics/ArmReach/left_stages.json').read_text())['rows']}
name=d[1]['actor'];prior=None
for line in Path('Saved/Diagnostics/ArmReach/left_stages.log').read_text(errors='replace').splitlines():
 if 'SlashSolveAudit,' not in line:continue
 v=line.split('SlashSolveAudit,')[1].split(',')
 if v[0]!=name or v[1]!='0':continue
 v=np.array(v[2:],float);t=121+round(v[0]*60);st=v[3:].reshape(-1,7)
 o,q,w=torso({n:x['future'] for n,x in d[t]['pose'].items()})
 world=[q*R.from_quat(s[3:]) for s in st]
 if prior is not None and 153<=t<=173:
  angles=[float((prior[i].inv()*world[i]).magnitude()*180/np.pi) for i in [0,2,4,7]]
  print(t,'raw S/H, pass1 S, pass2 S',np.round(angles,3),'pass2 vs raw',round(float((world[0].inv()*world[7]).magnitude()*180/np.pi),3))
 prior=world
