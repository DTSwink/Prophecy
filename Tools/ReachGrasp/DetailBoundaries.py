import json, pathlib, numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics/ReachGrasp20261012')
d=json.loads((p/'repeated-sim.json').read_text(encoding='utf-8'))
rows={r['tick']:r['actors']['BP_ProphecyManualPoseAgent_C_2'] for r in d['rows']}
def ang(a,b):return np.degrees((R.from_quat(a).inv()*R.from_quat(b)).magnitude())
print('fields',rows[378]['fields']);print('equipment',list(rows[378]['equipment']))
for start,end in [(360,386),(534,547),(975,985)]:
 for t in range(start,end+1):
    a,b=rows[t],rows[t-1]; x=a['authored'];hand=np.array(a['target']['hand_r']);prev=np.array(b['target']['hand_r']);pel=np.array(a['target']['pelvis']);pp=np.array(b['target']['pelvis']);
    body=x['bodyPose']; base=x['base']
    print(t,int(a['fields']['phase']), 'step',np.round((hand[:3]-pel[:3])-(prev[:3]-pp[:3]),2).tolist(), 'cmd/physdeg',round(ang(prev[3:],hand[3:]),2),round(ang(b['physical']['hand_r'][3:],a['physical']['hand_r'][3:]),2),'trackdeg',round(ang(hand[3:],a['physical']['hand_r'][3:]),2),'pole',round(x['poleAngle'],3), 'guide',x['guideTickA'],x['guideTickB'], 'fields', {k:round(v,3) for k,v in a['fields'].items() if k in ['hand','tip','angle','progress','reach_progress','insertion','returning','reach_done']})
