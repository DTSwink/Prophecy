import math
def mul(a,b):
 x,y,z,w=a;X,Y,Z,W=b
 return [w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z]
def rot(axis,deg):return [v*math.sin(math.radians(deg)/2) for v in axis]+[math.cos(math.radians(deg)/2)]
pa,qa,accepted=5.677611,183.957819,5.708538
damped=pa+(qa-pa)/(1+10/30)
for pitch0 in [20,40,60,80,100,120]:
 for pitch1 in [20,40,60,80,100,120]:
  for az in range(0,360,20):
   before=mul(rot([1,0,0],pa),rot([0,1,0],pitch0))
   proposed=mul(rot([1,0,0],qa),rot([0,math.cos(math.radians(az)),math.sin(math.radians(az))],pitch1))
   if sum(x*y for x,y in zip(before,proposed))<0:proposed=[-v for v in proposed]
   sn,cs=math.sin(math.radians(damped)/2),math.cos(math.radians(damped)/2)
   a=before[0]*cs-before[3]*sn;b=proposed[0]*cs-proposed[3]*sn
   alpha=a/(a-b) if abs(a-b)>1e-12 else 0
   if 0<=alpha<=1:continue
   alpha=max(0,min(1,alpha));q=[x*(1-alpha)+y*alpha for x,y in zip(before,proposed)];n=math.sqrt(sum(v*v for v in q));q=[v/n for v in q]
   out=mul(rot([1,0,0],accepted-damped),q)
   measured=math.degrees(2*math.atan2(out[0],out[3]));measured=accepted+(measured-accepted+180)%360-180
   print(dict(previous_pitch=pitch0,proposed_pitch=pitch1,azimuth=az,previous=pa,proposed=qa,wanted=accepted,actual=measured,alpha=alpha));raise SystemExit
