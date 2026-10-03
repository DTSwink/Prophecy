from pathlib import Path
import json,re,sys,math
from scipy.spatial.transform import Rotation as R
import numpy as np
p=Path(__file__).parent
for tag in sys.argv[1:]:
 d=json.loads((p/(tag+'.json')).read_text(encoding='utf-8'));assert not d['error'],d['error']
 rows=[r for r in d['rows'] if r['player']];assert len(rows)==400
 log=(p/(tag+'.log')).read_text(encoding='utf-8');m=re.search(r'WristIdleReference q=([\d.,-]+) axis=([\d.,-]+)',log)
 ref=R.from_quat([float(x) for x in m.group(1).split(',')]);up=np.array([float(x) for x in m.group(2).split(',')]);up/=np.linalg.norm(up)
 w=rows[0]['weapon'];i=max(range(3),key=lambda i:w['hi'][i]-w['lo'][i]);axis=np.eye(3)[i]
 hand_axis=R.from_quat(w['grip']['q']).apply(axis);idle=ref.apply(hand_axis);forward=idle-up*np.dot(idle,up);forward/=np.linalg.norm(forward)
 idle_elevation=math.degrees(math.asin(np.clip(np.dot(idle,up),-1,1)))
 out=[];previous=None
 for r in rows:
  q=R.from_quat(r['presented']['spine_05']['q']);direction=q.inv().apply(R.from_quat(r['weapon']['actual']['q']).apply(axis))
  yaw=math.degrees(math.atan2(np.dot(up,np.cross(forward,direction)),np.dot(forward,direction)))
  elevation=math.degrees(math.asin(np.clip(np.dot(up,direction),-1,1)))
  error=math.degrees(math.acos(np.clip(np.dot(direction,idle),-1,1)))
  step=math.degrees(math.acos(np.clip(np.dot(direction,previous),-1,1))) if previous is not None else 0;previous=direction
  expected=q.inv().apply(R.from_quat(r['presented']['hand_r']['q']).apply(hand_axis))
  actual_error=math.degrees(math.acos(np.clip(np.dot(direction,expected),-1,1)))
  out.append(dict(tick=r['tick'],yaw=yaw,elevation=elevation,idle_error=error,step=step,actual_vs_presented_error=actual_error))
 hold=[r for r in out if 191<=r['tick']<=341];fade=[r for r in out if 342<=r['tick']<=371]
 samples=[r for r in out if r['tick'] in (189,191,201,211,231,251,301,341,351,361,371,372)]
 summary=dict(idle_elevation=idle_elevation,first_within_5_1=next((r['tick'] for r in hold if r['idle_error']<=5.1),None),hold_end_error=hold[-1]['idle_error'],max_hold_step=max((r['step'],r['tick']) for r in hold),max_fade_step=max((r['step'],r['tick']) for r in fade),max_actual_target_error=max(r['actual_vs_presented_error'] for r in out if r['tick']>10),samples=samples)
 (p/(tag+'_split_metrics.json')).write_text(json.dumps(dict(summary=summary,rows=out),indent=2),encoding='utf-8')
 print(tag,json.dumps(summary))
