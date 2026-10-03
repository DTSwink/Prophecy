from pathlib import Path
s=Path('Saved/Diagnostics/ArmedSpineHitch/graph.txt').read_text(encoding='utf-16');lines=s.splitlines()
for i,l in enumerate(lines):
 if 'Set Upper Body Armed' in l:print('\n'.join(lines[i:i+34]))
import json,numpy as np
from scipy.spatial.transform import Rotation as R
p=Path('Saved/Diagnostics/Knee202/armed_spine_before.json')
if not p.exists():print('capture pending');raise SystemExit
rows=json.loads(p.read_text())['rows'];print('ticks',rows[0]['tick'],rows[-1]['tick'])
for stage in ['future','presented']:
 print(stage)
 for prev,row in zip(rows,rows[1:]):
  if not 125<=row['tick']<=160:continue
  bones=['spine_01','spine_05','head'];out=[]
  for b in bones:
   a=prev['raw'][b][stage];z=row['raw'][b][stage];angle=np.degrees((R.from_quat(a['q']).inv()*R.from_quat(z['q'])).magnitude());dist=np.linalg.norm(np.array(a['p'])-z['p']);out.append((b,round(angle,3),round(dist,3)))
  print(row['tick'],row['alpha'],out,row['attack'])
