import json,sys,math
from SummarizeHeadFps import angle
d=json.load(open(sys.argv[1]));name='BP_ProphecyManualPoseAgent_C_'+sys.argv[2];lo=int(sys.argv[3]);hi=int(sys.argv[4]);previous=None
for row in d['rows']:
 v=row['actors'][name];p=v['target'];n=row['tick']
 if lo<=n<=hi:
  a,b,c=[p[k][:3] for k in ('upperarm_r','lowerarm_r','hand_r')];u=[y-x for x,y in zip(a,b)];w=[y-x for x,y in zip(b,c)];l1=math.dist(a,b);l2=math.dist(b,c)
  bend=math.degrees(math.acos(max(-1,min(1,sum(x*y for x,y in zip(u,w))/(l1*l2)))))
  steps={k:round(angle(p[k],previous[k]),3) for k in ['clavicle_r','upperarm_r','lowerarm_r','hand_r','neck_01','neck_02','head']} if previous else {}
  print(n,{k:v['fields'].get(k) for k in ['phase','returning','slide_progress','pose_error','head_step']},'bend',round(bend,4),'extension',round(math.dist(a,c)/(l1+l2),6),'steps',steps)
 previous=p
