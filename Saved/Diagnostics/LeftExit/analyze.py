import json,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
folder=Path('Saved/Diagnostics/RunHandThigh')
def angle(a,b):return float(np.degrees((a*b.inv()).magnitude()))
for tag in ['left_exit_base','left_exit_no_twist','left_exit_slow_response','left_exit_no_inertia','left_exit_final_blend']:
 p=folder/(tag+'.json')
 if not p.exists():continue
 data=json.loads(p.read_text());rows={r['tick']:r for r in data['rows']};print(tag,data['error'])
 for t in [179,181,183,185,187,189,191,193,211,213]:
  a,b=rows[t-2]['future'],rows[t]['future'];q0=R.from_quat(a['lowerarm_l']['q']);q1=R.from_quat(b['lowerarm_l']['q'])
  ax0=np.array(a['hand_l']['p'])-a['lowerarm_l']['p'];ax0/=np.linalg.norm(ax0)
  ax1=np.array(b['hand_l']['p'])-b['lowerarm_l']['p'];ax1/=np.linalg.norm(ax1)
  swing=np.degrees(np.arccos(np.clip(ax0@ax1,-1,1)))
  print(t,'forearm',round(angle(q1,q0),2),'axis swing',round(swing,2),'spine-local',round(angle(R.from_quat(b['spine_05']['q']).inv()*q1,R.from_quat(a['spine_05']['q']).inv()*q0),2))
