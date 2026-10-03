import json, math, re, sys
from pathlib import Path
p = Path(__file__).parent
def mul(a,b):
 x,y,z,w=a;X,Y,Z,W=b
 return [w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z]
def inv(q): return [-q[0],-q[1],-q[2],q[3]]
def rot(q,v): return mul(mul(q,[*v,0]),inv(q))[:3]
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def cross(a,b): return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def axisq(v,a): return [*(x*math.sin(a/2) for x in v),math.cos(a/2)]
def qangle(a,b): return math.degrees(2*math.acos(min(1,abs(dot(a,b)))))
def local(r,ph='future'):return mul(inv(r[ph]['spine_05']['q']),r[ph]['hand_r']['q'])
def read(tag):
 d=json.loads((p/(tag+'.json')).read_text());assert not d['error'],d['error']
 return {x['tick']:x for x in d['rows'] if x['player']}
tag=sys.argv[1] if len(sys.argv)>1 else 'wrap_smooth_yaw'
a=read('wrap_horizontal_clamp'); b=read(tag)
g=json.loads((p/'wrap_horizontal_clamp_heading.json').read_text());up,forward,blade=g['up'],g['forward'],g['blade_axis']
audit=re.findall(r'WristTwist time=([\d.]+) weight=([\d.]+) proposed=([-\d.]+) accepted=([-\d.]+)',(p/'wrap_horizontal_clamp.log').read_text())
raw={}
for ts,w,proposed,accepted in audit:
 t=round(float(ts)*60);w=float(w);angle=float(proposed)
 correction=(max(-5,min(5,angle))-angle)*w
 raw[t]=mul(axisq(up,math.radians(-correction)),local(a[t]))
def heading(q):
 aim=rot(q,blade);flat=[v-dot(aim,up)*u for v,u in zip(aim,up)]
 return math.degrees(math.atan2(dot(up,cross(forward,flat)),dot(forward,flat)))
def elevation(q):return math.degrees(math.asin(max(-1,min(1,dot(rot(q,blade),up)))))
out={}
out['position_difference_cm']=max(math.dist(a[t][ph][bone]['p'],b[t][ph][bone]['p']) for t in a for ph in ('future','presented') for bone in ('upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r'))
out['left_rotation_difference_deg']=max(qangle(a[t]['future']['hand_l']['q'],b[t]['future']['hand_l']['q']) for t in a)
out['max_tilt_difference_from_raw_deg']=max(abs(elevation(local(b[t]))-elevation(q)) for t,q in raw.items())
out['max_correction_axis_error']=max(math.dist(rot(mul(local(b[t]),inv(q)),up),up) for t,q in raw.items())
out['motion']={}
for label,rr in [('rejected_clamp',a),('smooth_yaw',b)]:
 out['motion'][label]={
  'entry_step_189_to191_deg':qangle(local(rr[191]),local(rr[189])),
  'max_nn_step_191_371':max((qangle(local(rr[t]),local(rr[t-2])),t) for t in rr if t%2 and 191<=t<=371),
  'max_presented_step_190_371':max((qangle(local(rr[t],'presented'),local(rr[t-1],'presented')),t) for t in rr if 190<=t<=371),
  'fade_max_presented_step_339_375':max((qangle(local(rr[t],'presented'),local(rr[t-1],'presented')),t) for t in rr if 339<=t<=375),
  'samples':{t:dict(heading=heading(local(rr[t])),elevation=elevation(local(rr[t]))) for t in (189,191,193,201,211,227,251,269,301,341,369,371)}}
assert out['position_difference_cm']<1.e-4
assert out['left_rotation_difference_deg']<1.e-4
assert out['max_tilt_difference_from_raw_deg']<1.e-4
assert out['max_correction_axis_error']<1.e-6
assert out['motion']['smooth_yaw']['max_nn_step_191_371'][0]<70
assert out['motion']['smooth_yaw']['max_presented_step_190_371'][0]<35
assert out['motion']['smooth_yaw']['fade_max_presented_step_339_375'][0]<5
assert all(math.isfinite(v) for r in b.values() for ph in ('future','presented') for bone in r[ph].values() for k in ('p','q') for v in bone[k])
audit=(p/(tag+'.log')).read_text()
m=re.search(r'WristUnwind before=([-\d.]+) inward=([-\d.]+) center=([-\d.]+)',audit)
assert m
out['path']=dict(zip(('before','inward','center'),map(float,m.groups())))
assert out['path']['center']==360
previous=heading(local(b[189]));unwrapped=previous;path=[]
for t in range(191,342,2):
 h=heading(local(b[t]));unwrapped+=(h-previous+180)%360-180;previous=h;path.append((t,unwrapped))
out['unwrapped_heading_samples']=[(t,h) for t,h in path if t in (191,193,201,211,227,251,269,301,341)]
assert path[0][1]>out['path']['before']
assert min(h for t,h in path)>out['path']['inward']
(p/(tag+'_analysis.json')).write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
