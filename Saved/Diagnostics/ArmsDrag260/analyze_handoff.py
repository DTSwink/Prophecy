from pathlib import Path
import json,re,math,sys
import numpy as np
from scipy.spatial.transform import Rotation as R
p=Path(__file__).parent
for tag in sys.argv[1:]:
 d=json.loads((p/(tag+'.json')).read_text(encoding='utf-8'));assert not d['error'],d['error'];data=[r for r in d['rows'] if r['player']];assert len(data)==400
 log=(p/'wrap_handoff_before.log').read_text(encoding='utf-8');m=re.search(r'WristIdleReference q=([\d.,-]+) axis=([\d.,-]+)',log)
 ref=R.from_quat([float(x) for x in m.group(1).split(',')]);up=np.array([float(x) for x in m.group(2).split(',')]);up/=np.linalg.norm(up)
 axis=R.from_quat(data[0]['weapon']['grip']['q']).apply([0,0,1]);idle=ref.apply(axis);out=[];prev=None
 for row in data:
  f=row['presented'];sp=R.from_quat(f['spine_05']['q']);q=sp.inv()*R.from_quat(f['hand_r']['q']);pos=sp.inv().apply(np.array(f['hand_r']['p'])-f['spine_05']['p']);world=R.from_quat(row['weapon']['actual']['q']).apply([0,0,1]);blade=sp.inv().apply(world)
  x=dict(tick=row['tick'],p=pos.tolist(),q=q.as_quat().tolist(),blade=blade.tolist(),idle_error=math.degrees(math.acos(np.clip(blade@idle,-1,1))))
  x['posstep']=math.dist(pos,prev['p']) if prev else 0;x['qstep']=math.degrees((q*R.from_quat(prev['q']).inv()).magnitude()) if prev else 0;x['bladestep']=math.degrees(math.acos(np.clip(blade@np.array(prev['blade']),-1,1))) if prev else 0
  out.append(x);prev=x
 def stage(lo,hi):
  rr=[x for x in out if lo<=x['tick']<=hi];return dict(max_rotation_step=max((x['qstep'],x['tick']) for x in rr),max_position_step=max((x['posstep'],x['tick']) for x in rr),max_pointing_step=max((x['bladestep'],x['tick']) for x in rr))
 summary=dict(first_inside45=next((r['tick'] for r in out if r['tick']>=191 and r['idle_error']<=45),None),stationary_wrist_ticks=sum(1 for r in out if 220<=r['tick']<=281 and r['qstep']<1.e-4),hold=stage(191,281),blend=stage(283,311),handoff=stage(307,317),samples=[x for x in out if x['tick'] in (211,231,251,271,281,291,301,307,309,310,311,312,313,315)])
 (p/(tag+'_handoff_metrics.json')).write_text(json.dumps(dict(summary=summary,rows=out),indent=2),encoding='utf-8')
 print(tag,json.dumps({k:v for k,v in summary.items() if k!='samples'}))
