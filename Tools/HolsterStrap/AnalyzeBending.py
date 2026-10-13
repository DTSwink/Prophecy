"""Measure curl/twist/sideways motion in the solver's imported joint frames."""
import json,math,pathlib,sys
p=pathlib.Path(sys.argv[1]);d=json.loads(p.read_text());assert d['reason']=='completed'
def mul(a,b):
 x,y,z,w=a;X,Y,Z,W=b
 return [w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z]
def inv(q):return [-q[0],-q[1],-q[2],q[3]]
def normalize(q):
 n=math.sqrt(sum(v*v for v in q));return [v/n for v in q]
def angles(q):
 x,y,z,w=normalize(q);axis=[2*(x*y-z*w),1-2*(x*x+z*z),2*(y*z+x*w)]
 swing=normalize([axis[2],0,-axis[0],1+axis[1]])
 twist=mul(inv(swing),q)
 if twist[3]<0:twist=[-v for v in twist]
 return [math.degrees(2*math.asin(max(-1,min(1,v)))) for v in [swing[0],twist[1],swing[2]]]
rest=d['rest'];peak=[0.,0.,0.];by_bone={}
for i in range(1,6):
 name=f'strap_{i:02d}';parent=f'strap_{i-1:02d}'
 centre=[0.,0.,0.] if i==1 else angles(mul(inv(rest[parent][3:]),rest[name][3:]))
 local=[0.,0.,0.];ticks=[0,0,0]
 for row in d['rows']:
  if not row['running']:continue
  previous=rest[name][3:] if i==1 else row['bones'][parent][3:]
  a=angles(mul(inv(previous),row['bones'][name][3:]))
  for k in range(3):
   delta=abs((a[k]-centre[k]+180)%360-180)
   if delta>local[k]:local[k]=delta;ticks[k]=row['t']
 by_bone[name]={'curl_deg':local[0],'twist_deg':local[1],'side_deg':local[2],'peak_ticks':ticks}
 peak=[max(a,b) for a,b in zip(peak,local)]
result={'profile':d['profile'],'peak_curl_twist_side_deg':peak,'bones':by_bone}
if '--check' in sys.argv:
 # AnimDynamics enforces approximate limits: permit 1 degree of solver error.
 assert peak[1]<6 and peak[2]<3,result
 if not d.get('sideways'):assert peak[0]>5,'Curling was accidentally locked'
p.with_name(p.stem+'-bending.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
