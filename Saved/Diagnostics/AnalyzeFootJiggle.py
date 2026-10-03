import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics/Knee202/foot_jiggle_baseline.json')
if not p.exists():raise SystemExit('pending')
a=json.loads(p.read_text());print(a['reason'],len(a['rows']));rows={r['tick']:r for r in a['rows']};print('mode',rows[175]['mode'],'body',rows[175]['body_states']['foot_r'])
for t in range(165,187):
 r=rows[t];v=lambda b:np.array(r['meshes']['PhysicalMesh'][b]['p']);nn=np.array(r['raw']['foot_r']['presented']['p']);target=np.array(r['targets']['foot_r']['target']['p']);q=R.from_quat(r['meshes']['PhysicalMesh']['foot_r']['q']);nq=R.from_quat(r['raw']['foot_r']['presented']['q']);d=v('foot_r')-nn
 print(t,r['attack'],r['foot_owner'],'physical',np.round(v('foot_r'),3),'NN',np.round(nn,3),'offset',np.round(d,3),'rotErr',round(np.degrees((nq.inv()*q).magnitude()),3),'targetdiff',round(np.linalg.norm(target-nn),5))
