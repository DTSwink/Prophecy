import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R
root=pathlib.Path('Saved/Diagnostics/Knee202')
base={r['tick']:r for r in json.loads((root/'foot_jiggle_baseline.json').read_text())['rows']}
data=json.loads((root/'foot_jiggle_calf_aim.json').read_text())
print('Capture',data['reason'],len(data['rows']))
pre=0.;foot_change=0.
for r in data['rows']:
 t=r['tick'];old=base.get(t)
 if not old:continue
 if t<167:
  pre=max(pre,*[np.linalg.norm(np.array(r['raw'][b]['presented']['p'])-old['raw'][b]['presented']['p']) for b in r['raw']])
 if 173<=t<=182:
  b='foot_r';nn=r['raw'][b]['presented'];c=r['raw']['calf_r']['presented']
  err=np.linalg.norm(np.array(r['meshes']['PhysicalMesh'][b]['p'])-nn['p'])
  before=np.linalg.norm(np.array(old['meshes']['PhysicalMesh'][b]['p'])-old['raw'][b]['presented']['p'])
  local=R.from_quat(c['q']).inv().apply(np.array(nn['p'])-c['p'])
  change=np.linalg.norm(np.array(nn['p'])-old['raw'][b]['presented']['p']);foot_change=max(foot_change,change)
  print(t,'error cm',round(before,5),'->',round(err,5),'NN foot change',round(change,6),'calf local',np.round(local,5))
print('Max pre-recovery NN position change',pre,'Max window foot change',foot_change)
