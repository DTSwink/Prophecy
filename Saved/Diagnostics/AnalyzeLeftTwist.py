exec(open('Saved/Diagnostics/AnalyzeLeftSolve.py').read().split('name=d[1]')[0])
def unit(x):return x/max(np.linalg.norm(x),1e-15)
def plane(v,a):return unit(v-a*(v@a))
def between(a,b):
 a=unit(a);b=unit(b);return R.from_quat(np.r_[np.cross(a,b),1+a@b]/np.linalg.norm(np.r_[np.cross(a,b),1+a@b]))
def hinge(s,w,lu):
 upper=R.from_quat(s[3:]).apply(lu);axis=unit(w[:3]-s[:3]);pole=plane(upper,axis)
 return upper,axis,pole,unit(np.cross(axis,pole))
def transport(a,b,p):return plane(p-(a+b)*((p@b)/(1+a@b)),b)
def smooth(x):x=np.clip(x,0,1);return x*x*(3-2*x)
import sys
tag=sys.argv[1] if len(sys.argv)>1 else 'left_stages'
elbows={};solves={}
for line in Path('Saved/Diagnostics/ArmReach/'+tag+'.log').read_text(errors='replace').splitlines():
 if 'SlashElbowAudit,' in line:
  v=line.split('SlashElbowAudit,')[1].split(',')
  if v[0]==d[1]['actor']:
   a=np.array(v[1:],float);elbows.setdefault(round(a[0],6),a)
 if 'SlashSolveAudit,' in line:
  v=line.split('SlashSolveAudit,')[1].split(',')
  if v[0]==d[1]['actor'] and v[1]=='0':a=np.array(v[2:],float);solves[round(a[0],6)]=a
for time in sorted(solves):
 if not .5<time<.8:continue
 log=solves[time];e=elbows[time];alpha=log[2];st=log[3:].reshape(-1,7);ps=e[30:37];pw=e[44:51];s=st[0];w=st[2];lu=e[3:6];target=st[3][:3]
 P=hinge(ps,pw,lu);N=hinge(s,w,lu);axis=unit(target-s[:3]);prior=transport(P[1],axis,P[2]);nxt=transport(N[1],axis,N[2]);cos=np.clip(prior@nxt,-1,1)
 trust=smooth(np.linalg.norm(N[0]-N[1]*(N[0]@N[1]))/(np.linalg.norm(lu)*.02))*smooth((1+N[1]@axis)/.05)*smooth((1+cos)/.02)
 weight=alpha*trust;angle=np.arctan2(axis@np.cross(prior,nxt),cos);pole=R.from_rotvec(axis*angle*weight).apply(prior)
 length1=np.linalg.norm(lu);length2=(1-alpha)*np.linalg.norm(pw[:3]-e[37:44][:3])+alpha*np.linalg.norm(w[:3]-st[1][:3]);distance=np.clip(np.linalg.norm(target-s[:3]),abs(length1-length2),length1+length2)
 along=(length1**2-length2**2+distance**2)/(2*distance);upper=axis*along+pole*np.sqrt(max(0,length1**2-along**2));normal=unit(np.cross(axis,pole))
 def frame(h,rot):
  swing=between(h[0],upper);twist=between(swing.apply(h[3]),normal);return twist*swing*rot
 f0=frame(P,R.from_quat(ps[3:]));f1=frame(N,R.from_quat(s[3:]));q=(f1*f0.inv()).as_quat();signed=(2*np.arctan2(q[:3]@unit(upper),q[3])+np.pi)%(2*np.pi)-np.pi
 print(round(time,4),'radius',round(np.linalg.norm(N[0]-N[1]*(N[0]@N[1])),3),'solvedRadius',round(np.sqrt(max(0,length1**2-along**2)),3),'aim',round(N[1]@axis,3),'weight',round(weight,5),'twist',round(np.degrees(signed),3),'pole angle',round(np.degrees(angle),3))
