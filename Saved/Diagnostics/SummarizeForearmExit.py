import json,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
p=Path('Saved/Diagnostics/ForearmExit')
a={r['tick']:r for r in json.loads((p/'legacy.json').read_text())['rows'] if r['possessed']};b={r['tick']:r for r in json.loads((p/'fixed.json').read_text())['rows'] if r['possessed']}
summary={'prefix_max_position_cm':0.,'prefix_max_quaternion_component':0.,'windows':[]}
for t in range(1,115):
 for bone in a[t]['pose']:
  u=a[t]['pose'][bone]['future'];v=b[t]['pose'][bone]['future']
  summary['prefix_max_position_cm']=max(summary['prefix_max_position_cm'],float(np.linalg.norm(np.array(u['p'])-v['p'])))
  summary['prefix_max_quaternion_component']=max(summary['prefix_max_quaternion_component'],float(np.max(np.abs(np.array(u['q'])-v['q']))))
for start in [115,205,295]:
 w={'start':start}
 for tag in ['legacy','fixed']:
  rows=json.loads((p/(tag+'-angles.json')).read_text());seg=[r for r in rows if start<=r['tick']<start+60]
  w[tag]={'roll_net_degrees':sum(r['froll'] for r in seg),'roll_travel_degrees':sum(abs(r['froll']) for r in seg),'max_policy_rotation_step_degrees':max(r['fstep'] for r in seg)}
 summary['windows'].append(w)
print(json.dumps(summary,indent=2));(p/'summary.json').write_text(json.dumps(summary,indent=2))
