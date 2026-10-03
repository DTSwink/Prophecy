import json,math,re,sys
from pathlib import Path
p=Path(__file__).parent
def mul(a,b):
 x,y,z,w=a;X,Y,Z,W=b
 return [w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z]
def inv(q):return [-q[0],-q[1],-q[2],q[3]]
def rot(q,v):return mul(mul(q,[*v,0]),inv(q))[:3]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def norm(a):return [x/math.sqrt(dot(a,a)) for x in a]
def project(a,u):return [x-dot(a,u)*y for x,y in zip(a,u)]
def delta(x):return (x+180)%360-180
def angle(a,b):return math.degrees(math.acos(max(-1,min(1,dot(a,b)))))
for tag in sys.argv[1:]:
 d=json.loads((p/(tag+'.json')).read_text());assert not d['error']
 rows=[r for r in d['rows'] if r['player']];assert len(rows)==400
 log=(p/(tag+'.log')).read_text(errors='replace')
 m=re.search(r'WristIdleReference q=([\d.,-]+) axis=([\d.,-]+)',log)
 ref,up=([float(x) for x in g.split(',')] for g in m.groups());up=norm(up)
 w=rows[0]['weapon'];axis=max(range(3),key=lambda i:w['hi'][i]-w['lo'][i]);center=[(x+y)/2 for x,y in zip(w['lo'],w['hi'])]
 ends=[]
 for z in (w['lo'][axis],w['hi'][axis]):
  v=center.copy();v[axis]=z;q=rot(w['grip']['q'],[x*s for x,s in zip(v,w['scale'])]);ends.append([x+y for x,y in zip(q,w['grip']['p'])])
 tip_sign=1 if dot(ends[1],ends[1])>dot(ends[0],ends[0]) else -1
 blade_mesh=[0,0,0];blade_mesh[axis]=tip_sign
 hand_axis=rot(w['grip']['q'],blade_mesh)
 idle=norm(project(rot(ref,hand_axis),up));out=[];last=None
 for r in rows:
  w=r['weapon'];world=norm(rot(w['actual']['q'],blade_mesh));spine=rot(inv(r['presented']['spine_05']['q']),world)
  actual_heading=math.degrees(math.atan2(dot(up,cross(idle,spine)),dot(idle,spine)))
  rendered_target=norm(rot(r['presented']['hand_r']['q'],rot(w['grip']['q'],blade_mesh)))
  future_target=norm(rot(r['future']['hand_r']['q'],rot(w['grip']['q'],blade_mesh)))
  world_heading=math.degrees(math.atan2(world[1],world[0]));elevation=math.degrees(math.asin(max(-1,min(1,dot(spine,up)))))
  inward=rot(inv(r['presented']['spine_05']['q']),[x-y for x,y in zip(r['presented']['spine_05']['p'],r['presented']['hand_r']['p'])])
  torso_angle=angle(norm(project(spine,up)),norm(project(inward,up)))
  x=dict(tick=r['tick'],attack=r['attack'],world_direction=world,spine_direction=spine,spine_heading=actual_heading,world_heading=world_heading,elevation=elevation,
   rendered_target_error_deg=angle(world,rendered_target),future_target_error_deg=angle(world,future_target),toward_torso_angle=torso_angle)
  x['spine_step']=delta(actual_heading-last['spine_heading']) if last else 0
  x['world_step']=delta(world_heading-last['world_heading']) if last else 0
  x['direction_step_3d']=angle(world,last['world_direction']) if last else 0
  x['unwrapped_spine_heading']=(last['unwrapped_spine_heading']+x['spine_step']) if last else actual_heading
  out.append(x);last=x
 stages={}
 for label,lo,hi in [('pre_attack',1,152),('attack',153,190),('hold',191,341),('blend_out',342,371),('after',372,400)]:
  rr=[x for x in out if lo<=x['tick']<=hi]
  stages[label]=dict(range=[lo,hi],start=rr[0]['unwrapped_spine_heading'],end=rr[-1]['unwrapped_spine_heading'],
   clockwise_degrees=sum(max(0,x['spine_step']) for x in rr),counterclockwise_degrees=-sum(min(0,x['spine_step']) for x in rr),
   max_world_3d_step=max((x['direction_step_3d'],x['tick']) for x in rr),min_torso_angle=min((x['toward_torso_angle'],x['tick']) for x in rr),
   min_elevation=min(x['elevation'] for x in rr),max_elevation=max(x['elevation'] for x in rr))
 summary=dict(tag=tag,source='actual sword mesh quaternion, not NN hand quaternion',mesh_axis=axis,tip_sign=tip_sign,
  max_presented_target_error_after_start=max(x['rendered_target_error_deg'] for x in out if x['tick']>10),stages=stages,
  samples=[{k:x[k] for k in ('tick','spine_heading','elevation','world_direction','toward_torso_angle')} for x in out if x['tick'] in (153,169,177,189,191,201,211,227,251,269,301,341,351,361,371,391)])
 (p/(tag+'_actual_sword.json')).write_text(json.dumps(dict(summary=summary,rows=out),indent=2))
 print(json.dumps(summary,indent=2))
