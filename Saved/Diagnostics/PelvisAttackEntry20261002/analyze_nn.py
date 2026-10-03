import json,sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
p=Path(__file__).resolve().parent
mode=sys.argv[1] if len(sys.argv)>1 else 'baseline'
rows=[json.loads(l) for l in (p/(mode+'-nn.jsonl')).read_text(encoding='utf8').splitlines() if l.strip()]
def world(r,pos):
 # Training local maps (x,y,z) to UE (x,-z,y) before anchor rotation.
 local=(np.array(pos)-r['native_position'])@np.array(r['native_rotation']).reshape(3,3).T
 return R.from_quat(r['anchor'][3:]).apply(local*[100,-100,100])+r['anchor'][:3]
for r in rows:
 if r['actor'].endswith('_0') and r['frame']<=7:
  # Recurrent lower positions are already in the anchor's local training frame.
  def state(pos): return R.from_quat(r['anchor'][3:]).apply(np.array(pos)*[100,-100,100])+r['anchor'][:3]
  print(r['actor'],r['family'],r['frame'],'time',round(r['time'],5),'prior',np.round(state(r['input'][:3]),3),'current',np.round(state(r['input'][41:44]),3),'output',np.round(world(r,r['output'][131:134]),3),'anchor',np.round(r['anchor'][:3],3))
