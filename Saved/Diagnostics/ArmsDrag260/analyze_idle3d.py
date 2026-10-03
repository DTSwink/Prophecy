import sys,json,re,math
from pathlib import Path
from scipy.spatial.transform import Rotation as R
args=sys.argv[1:];sys.argv=sys.argv[:1]
from idle_route_probe import segment_distance
p=Path(__file__).parent
for tag in args:
 data=json.loads((p/(tag+'.json')).read_text(encoding='utf-8'));assert not data['error'],data['error']
 rows=[r for r in data['rows'] if r['player']];assert len(rows)==400
 ref=R.from_quat([float(x) for x in re.search(r'WristIdleReference q=([\d.,-]+)',(p/(tag+'.log')).read_text(encoding='utf-8')).group(1).split(',')])
 w=rows[0]['weapon'];center=[(a+b)*.5 for a,b in zip(w['lo'],w['hi'])];axis=max(range(3),key=lambda i:w['hi'][i]-w['lo'][i]);blade=[]
 for z in (w['lo'][axis],w['hi'][axis]):
  v=center.copy();v[axis]=z;blade.append(R.from_quat(w['grip']['q']).apply([a*b for a,b in zip(v,w['scale'])])+w['grip']['p'])
 out=[];last=None;last_direction=None
 hand_axis=(blade[1]-blade[0]);hand_axis=hand_axis/math.sqrt(sum(hand_axis**2))
 for row in rows:
  f=row['presented'];q=R.from_quat(f['spine_05']['q']);hand=R.from_quat(f['hand_r']['q']);local=q.inv()*hand
  pelvis=f['pelvis']['p'];sp=f['spine_05']['p'];rad=.5*math.dist(f['upperarm_l']['p'],f['upperarm_r']['p'])+1
  ends=[hand.apply(b)+f['hand_r']['p'] for b in blade]
  clearance=segment_distance(*ends,pelvis,sp)-rad
  actual=R.from_quat(row['weapon']['actual']['q']);direction=actual.apply([int(i==axis) for i in range(3)])
  local_direction=local.apply(hand_axis)
  error=math.degrees(math.acos(max(-1,min(1,float(local_direction@ref.apply(hand_axis))))))
  step=math.degrees(math.acos(max(-1,min(1,float(local_direction@last_direction))))) if last_direction is not None else 0;last_direction=local_direction
  out.append(dict(tick=row['tick'],error=error,clearance=clearance,step=step,direction=direction.tolist()))
 stats={}
 for name,lo,hi in [('hold',191,341),('blend',342,371),('release',372,400)]:
  rr=[x for x in out if lo<=x['tick']<=hi]
  stats[name]=dict(max_step=max((x['step'],x['tick']) for x in rr),minimum_clearance=min((x['clearance'],x['tick']) for x in rr),last_error=rr[-1]['error'],penetrating_ticks=[x['tick'] for x in rr if x['clearance']<0])
 baseline=[r for r in json.loads((p/'wrap_smooth_yaw.json').read_text(encoding='utf-8'))['rows'] if r['player']]
 stats['max_arm_position_change']=max(math.dist(r[pose][b]['p'],old[pose][b]['p']) for r,old in zip(rows,baseline) for pose in ['future','presented'] for b in ['upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r'])
 stats['max_left_rotation_change']=max(math.degrees((R.from_quat(r['presented']['hand_l']['q'])*R.from_quat(old['presented']['hand_l']['q']).inv()).magnitude()) for r,old in zip(rows,baseline))
 (p/(tag+'_3d_metrics.json')).write_text(json.dumps(dict(stats=stats,rows=out),indent=2),encoding='utf-8')
 print(tag,json.dumps(stats))
