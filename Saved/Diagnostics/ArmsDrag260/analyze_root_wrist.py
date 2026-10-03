from pathlib import Path
import json,math,re,sys
import numpy as np
from scipy.spatial.transform import Rotation as R
p=Path(__file__).parent
for tag in sys.argv[1:]:
 data=json.loads((p/(tag+'.json')).read_text(encoding='utf-8'));assert not data['error'],data['error']
 rows=[r for r in data['rows'] if r['player']];assert len(rows)==400
 match=re.search(r'WristIdleReference q=([\d.,-]+) axis=([\d.,-]+)',(p/(tag+'.log')).read_text(encoding='utf-8'))
 ref=R.from_quat([float(x) for x in match[1].split(',')])
 axis=R.from_quat(rows[0]['weapon']['grip']['q']).apply([0,0,1]);idle=ref.apply(axis)
 forward=idle.copy();forward[2]=0;forward/=np.linalg.norm(forward)
 out=[];previous=None
 for row in rows:
  f=row['presented'];rt=f.get('root',row['meshes']['PhysicalMesh']['root']);root=R.from_quat(rt['q'])
  world=R.from_quat(row['weapon']['actual']['q']).apply([0,0,1]);aim=root.inv().apply(world)
  q=root.inv()*R.from_quat(f['hand_r']['q']);pos=root.inv().apply(np.array(f['hand_r']['p'])-rt['p'])
  x=dict(tick=row['tick'],idle_error=math.degrees(math.acos(np.clip(aim@idle,-1,1))),yaw=math.degrees(math.atan2(np.cross(forward,aim)[2],forward@aim)),world_elevation=math.degrees(math.asin(np.clip(world[2],-1,1))),idle_world_elevation=math.degrees(math.asin(np.clip(root.apply(idle)[2],-1,1))),q=q.as_quat().tolist(),aim=aim.tolist(),p=pos.tolist())
  x['qstep']=math.degrees((q*R.from_quat(previous['q']).inv()).magnitude()) if previous else 0
  x['aimstep']=math.degrees(math.acos(np.clip(aim@np.array(previous['aim']),-1,1))) if previous else 0
  x['posstep']=math.dist(pos,previous['p']) if previous else 0
  out.append(x);previous=x
 def phase(lo,hi):
  rr=[r for r in out if lo<=r['tick']<=hi]
  return dict(max_rotation_step=max((r['qstep'],r['tick']) for r in rr),max_pointing_step=max((r['aimstep'],r['tick']) for r in rr),max_position_step=max((r['posstep'],r['tick']) for r in rr),max_error=max(r['idle_error'] for r in rr),world_elevation=[min(r['world_elevation'] for r in rr),max(r['world_elevation'] for r in rr)])
 summary=dict(idle_root_direction=idle.tolist(),first_inside15=next((r['tick'] for r in out if r['tick']>=191 and r['idle_error']<=15),None),hold=phase(191,281),reported=phase(220,250),fade=phase(283,311),handoff=phase(307,317),samples=[{k:r[k] for k in ('tick','yaw','idle_error','world_elevation','idle_world_elevation','qstep','posstep')} for r in out if r['tick'] in (191,200,210,220,230,240,250,281,301,309,310,311,312,313)])
 (p/(tag+'_root_metrics.json')).write_text(json.dumps(dict(summary=summary,rows=out),indent=2),encoding='utf-8')
 print(tag,json.dumps(summary))
