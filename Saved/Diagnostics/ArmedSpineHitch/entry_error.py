import json,numpy as np
from scipy.spatial.transform import Rotation as R
from pathlib import Path
rows={r['tick']:r for r in json.loads(Path('Saved/Diagnostics/Knee202/armed_spine_before.json').read_text())['rows']}
for bone in ['pelvis','spine_01','spine_05','head']:
 old=rows[138]['raw'][bone]['future'];shown=rows[140]['raw'][bone]['presented']
 print(bone,'history change deg',np.degrees((R.from_quat(old['q']).inv()*R.from_quat(shown['q'])).magnitude()),'cm',np.linalg.norm(np.array(old['p'])-shown['p']))
