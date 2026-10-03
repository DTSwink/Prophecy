"""Independent double-precision evaluation of the recorded planted-leg fixture."""
import pathlib,re,json,math
import numpy as np
from scipy.spatial.transform import Rotation,Slerp
from ReplayTemperedLeg import unit,project,rot,mixrot
p=pathlib.Path(__file__).resolve().parents[2]
text=(p/'Source/GameAnimationSample3/Private/ProphecyKneeStanceTests.inl').read_text().split('// PelvisHitch-20260920')[0]
arrays=re.findall(r'^        \{([^{}]+)\}',text,re.M)
def nums(s):return np.array([float(x.strip().rstrip('f')) for x in s.split(',')])
prev,nn,target=[np.r_[nums(s)[:9],np.zeros(16),nums(s)[9:]] for s in arrays if len(s.split(','))==25]
hipoff=np.array([-.025693262,.0001087198034,.07750071585])
kneeoff=np.array([.3886490762,.001097515225,.00004229974002])
footlocal=unit(np.array([.06159852445,.1382641196,-.006806043908]))
L1=np.linalg.norm(kneeoff);L2=.4256333665
def smooth(v):v=np.clip(v,0,1);return v*v*(3-2*v)
def axisrot(axis,angle):return Rotation.from_rotvec(axis*angle).as_matrix().T
def hip(s):return s[:3]+hipoff@rot(s,3)
H=hip(target);axis=unit(target[25:28]-H)
def solve(s):
 oldupper=kneeoff@rot(s,34);olda=unit(s[25:28]-hip(s));oldp=project(oldupper,olda)
 pole=project(oldp-(olda+axis)*np.dot(oldp,axis)/(1+np.dot(olda,axis)),axis)
 d=np.linalg.norm(target[25:28]-H);along=(L1*L1-L2*L2+d*d)/(2*d)
 upper=axis*along+pole*np.sqrt(L1*L1-along*along)
 oldn=unit(np.cross(olda,oldp));newn=unit(np.cross(axis,pole))
 ob=np.array([unit(oldupper),unit(np.cross(oldn,unit(oldupper))),oldn])
 nb=np.array([unit(upper),unit(np.cross(newn,unit(upper))),newn])
 return rot(s,34)@ob.T@nb,pole
toe=footlocal@rot(target,28);forward=unit(toe*[1,1,0]);side=np.cross([0,0,1],forward)
src=nn.copy();srctoe=footlocal@rot(src,28);srcforward=unit(srctoe*[1,1,0])
heading=math.atan2(np.cross(srcforward,forward)[2],np.dot(srcforward,forward))
turn=axisrot(np.array([0,0,1]),heading)
src[25:28]=hip(src)+(src[25:28]-hip(src))@turn
for o in (28,34):src[o:o+6]=(rot(src,o)@turn)[:2].ravel()
baseweight=smooth(np.linalg.norm(srctoe*[1,1,0])**2*4)*smooth(np.linalg.norm(toe*[1,1,0])**2*4)
diff=Rotation.from_matrix(rot(prev,34)@rot(src,34).T).magnitude()
baseweight*=min(1,math.radians(20)/max(diff,1e-6))
R0,P0=solve(prev);R1,P1=solve(src)
cos=np.clip(np.dot(P0,P1),-1,1);sourceaxis=unit(src[25:28]-hip(src));su=kneeoff@rot(src,34)
radius=np.linalg.norm(su-sourceaxis*np.dot(su,sourceaxis))
trust=smooth(radius/(L1*.02))*smooth((1+cos)/.02)*smooth((1+np.dot(sourceaxis,axis))/.05)
bendangle=math.atan2(np.dot(axis,np.cross(P0,P1)),cos)
def final(follow,new,plane_follow=False):
 w=baseweight*trust*(follow if new else 1)
 a=R0@axisrot(axis,bendangle*w);b=R1@axisrot(axis,-bendangle*(1-w))
 thigh=mixrot(a,b,w);upper=kneeoff@thigh;along=np.dot(upper,axis)
 radial=upper-axis*along;radius=np.linalg.norm(radial);pole=unit(radial)
 sa=np.dot(axis,side);n0=side-axis*sa;nlen=np.linalg.norm(n0);N=unit(n0);hp=unit(np.cross(axis,N))
 transported=np.dot(upper,side)
 def lateral(s):
  t=footlocal@rot(s,28);f=unit(t*[1,1,0]);offset=np.dot(kneeoff@rot(s,34),np.cross([0,0,1],f))
  conf=smooth(np.linalg.norm(t*[1,1,0])**2*4)
  return transported*(1-conf)+offset*conf
 sw=w if new else w*follow
 desired=lateral(prev)*(1-sw)+lateral(src)*sw
 q=(desired-along*sa)/(radius*nlen);branch=np.dot(pole,hp)
 strength=(follow if plane_follow else 1)*smooth(np.linalg.norm(toe*[1,1,0])**2*4)*smooth(nlen*nlen*4)*smooth((1-abs(q))*4)*smooth(abs(branch)*4)
 cq=np.clip(q,-1,1);dp=N*cq+hp*np.sign(branch)*np.sqrt(max(0,1-cq*cq))
 angle=math.atan2(np.dot(axis,np.cross(pole,dp)),np.clip(np.dot(pole,dp),-1,1))
 out=thigh@axisrot(axis,angle*strength)
 return dict(rotation6=out[:2].ravel().tolist(),step_deg=math.degrees(Rotation.from_matrix(out@rot(prev,34).T).magnitude()),
  source_follow=w,plane_strength=float(strength),desired_side=desired,actual_side=float(np.dot(kneeoff@out,side)),
  calf_length=float(np.linalg.norm(target[25:28]-H-kneeoff@out)))
results={'old':final(.1,False),'new':final(.1,True),'candidate':final(.1,True,True),
 'quarter_candidate':[final(f,True,True) for f in (.23,.24,.25,.26,.27)],
 'sweep':[final(f,True,True) for f in np.linspace(.01,1,100)]}
print(json.dumps({k:v for k,v in results.items() if k!='sweep'},indent=2))
(p/'Saved/Diagnostics/SupportFollow-geometry.json').write_text(json.dumps(results,indent=2))
