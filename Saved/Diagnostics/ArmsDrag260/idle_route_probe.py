import json,math,re
from pathlib import Path
from analyze_actual_sword import mul,inv,rot,dot,norm
p=Path(__file__).parent
def sub(a,b):return [x-y for x,y in zip(a,b)]
def add(a,b):return [x+y for x,y in zip(a,b)]
def scale(a,s):return [x*s for x in a]
def clamp(x,a=0,b=1):return max(a,min(b,x))
def segment_distance(p1,q1,p2,q2):
 d1=sub(q1,p1);d2=sub(q2,p2);r=sub(p1,p2);a=dot(d1,d1);e=dot(d2,d2);f=dot(d2,r)
 if a<1e-12:s=0;t=clamp(f/e) if e else 0
 else:
  c=dot(d1,r)
  if e<1e-12:t=0;s=clamp(-c/a)
  else:
   b=dot(d1,d2);den=a*e-b*b;s=clamp((b*f-c*e)/den) if den else 0;t=(b*s+f)/e
   if t<0:t=0;s=clamp(-c/a)
   elif t>1:t=1;s=clamp((b-c)/a)
 return math.dist(add(p1,scale(d1,s)),add(p2,scale(d2,t)))
r={x['tick']:x for x in json.loads((p/'wrap_smooth_yaw.json').read_text())['rows'] if x['player']}
ref=[float(x) for x in re.search(r'WristIdleReference q=([\d.,-]+)',(p/'wrap_smooth_yaw.log').read_text()).group(1).split(',')]
w=r[189]['weapon'];center=[(x+y)/2 for x,y in zip(w['lo'],w['hi'])];blade=[]
for z in (w['lo'][2],w['hi'][2]):
 v=center.copy();v[2]=z;blade.append(add(rot(w['grip']['q'],[x*s for x,s in zip(v,w['scale'])]),w['grip']['p']))
def geometry(t):
 f=r[t]['future'];sp=f['spine_05'];q=inv(sp['q']);base=rot(q,sub(f['pelvis']['p'],sp['p']));hand=rot(q,sub(f['hand_r']['p'],sp['p']));rad=.5*math.dist(f['upperarm_l']['p'],f['upperarm_r']['p'])+1
 return base,hand,rad
def clearance(q,t):
 base,hand,rad=geometry(t);a,b=[add(hand,rot(q,v)) for v in blade]
 return segment_distance(a,b,base,[0,0,0])-rad
if __name__=='__main__':
 print('idle clearance',[(t,round(clearance(ref,t),2)) for t in (189,191,201,211,227,241,251,269,301,341,361)])
 print('minimum idle clearance',min((clearance(ref,t),t) for t in range(191,342)))
