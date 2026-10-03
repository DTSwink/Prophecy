import json,numpy as np
from scipy.spatial.transform import Rotation as R
from pathlib import Path
out={}
for tag in ['before','after']:
 data=json.loads(Path(f'Saved/Diagnostics/Knee202/armed_spine_{tag}.json').read_text());rows={r['tick']:r for r in data['rows']}
 assert data['reason']=='Complete'
 result={}
 for bone in ['pelvis','spine_01','spine_05','head']:
  old=rows[138]['raw'][bone]['future'];shown=rows[140]['raw'][bone]['presented']
  result[bone]={'history_jump_deg':float(np.degrees((R.from_quat(old['q']).inv()*R.from_quat(shown['q'])).magnitude())),'history_jump_cm':float(np.linalg.norm(np.array(old['p'])-shown['p']))}
 out[tag]=result
print(json.dumps(out,indent=2));Path('Saved/Diagnostics/ArmedSpineHitch/comparison.json').write_text(json.dumps(out,indent=2))
assert out['after']['spine_05']['history_jump_deg']<.001
assert out['after']['head']['history_jump_cm']<.001
