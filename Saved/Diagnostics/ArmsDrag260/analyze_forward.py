import json,math,re,sys
from pathlib import Path
p=Path(__file__).parent;tag=sys.argv[1] if len(sys.argv)>1 else 'wrap_forward_blade_before'
d=json.loads((p/(tag+'.json')).read_text());assert not d['error'];r={x['tick']:x for x in d['rows'] if x['player']}
def mul(a,b):
 x,y,z,w=a;X,Y,Z,W=b
 return [w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z]
def inv(q):return [-q[0],-q[1],-q[2],q[3]]
def rot(q,v):return mul(mul(q,[*v,0]),inv(q))[:3]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def norm(a):
 l=math.sqrt(dot(a,a));return [x/l for x in a]
def project(a,n):return [x-dot(a,n)*y for x,y in zip(a,n)]
def local(x,phase='future'):return mul(inv(x[phase]['spine_05']['q']),x[phase]['hand_r']['q'])
w=next(x['weapon'] for x in r.values() if 'weapon' in x);i=max(range(3),key=lambda i:w['hi'][i]-w['lo'][i]);v=[0,0,0];v[i]=1
center=[(x+y)/2 for x,y in zip(w['lo'],w['hi'])];ends=[]
for val in [w['lo'][i],w['hi'][i]]:
 vv=center.copy();vv[i]=val;vv=rot(w['grip']['q'],[x*y for x,y in zip(vv,w['scale'])]);ends.append([x+y for x,y in zip(vv,w['grip']['p'])])
sgn=1 if dot(ends[1],ends[1])>dot(ends[0],ends[0]) else -1
v=[sgn*x for x in rot(w['grip']['q'],v)]
log=(p/(tag+'.log')).read_text(errors='replace');m=re.search(r'WristIdleReference q=([\d.,-]+) axis=([\d.,-]+)',log)
ref,up=([float(x) for x in g.split(',')] for g in m.groups());forward=norm(project(rot(ref,v),up))
out=[]
for t,x in r.items():
 blade=rot(local(x),v);flat=project(blade,up);heading=math.degrees(math.atan2(dot(up,cross(forward,flat)),dot(forward,flat)))
 out.append(dict(tick=t,heading=heading,elevation=math.degrees(math.asin(max(-1,min(1,dot(blade,up)))))))
print('HAND BLADE AXIS',v,'IDLE FORWARD',forward)
print([x for x in out if x['tick'] in [1,189,191,201,211,221,225,227,229,231,241,251,261,269,271,301]])
(p/(tag+'_heading.json')).write_text(json.dumps(dict(blade_axis=v,forward=forward,up=up,rows=out),indent=2))
