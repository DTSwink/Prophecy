import json,re
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
d=json.loads(Path('Saved/Diagnostics/Pin216.json').read_text())
for r in d['rows']:
 if r['tick'] not in (213,214,215,216,217,218,223,225):continue
 root=r['roots'][0];h=Rotation.from_quat(r['roots'][7]['q']).apply([0,1,0]);h[2]=0;h/=np.linalg.norm(h)
 vals={}
 for s in ('l','r'):
  vals[s]=[]
  for foot in r['targets']['foot_'+s]:
   dist=float(np.dot(np.array(root['p'])-foot['p'],h));cap=float(np.clip((50-dist)/30,0,1))
   vals[s].append((round(dist,5),round(cap,6)))
 print(r['tick'],r['pin'],vals)
