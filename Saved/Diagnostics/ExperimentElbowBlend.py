import json,numpy as np
from scipy.spatial.transform import Rotation as R,Slerp
from pathlib import Path
d=json.loads(Path('Saved/Diagnostics/ElbowStages.json').read_text())[0]
def unit(v):return v/max(1e-12,np.linalg.norm(v))
def plane(v,a):return unit(v-a*np.dot(v,a))
def transport(p,old,new):return plane(p-(old+new)*np.dot(p,new)/(1+np.dot(old,new)),new)
prev=np.array(d['previous']);idle=np.array(d['neutral']);target=np.array(d['h']);offset=np.array(d['localUpper']);axis=unit(target-idle[0,:3])
goal=transport(plane(idle[1,:3]-idle[0,:3],unit(idle[2,:3]-idle[0,:3])),unit(idle[2,:3]-idle[0,:3]),axis)
oldAxis=unit(prev[2,:3]-prev[0,:3]);prior=transport(plane(prev[1,:3]-prev[0,:3],oldAxis),oldAxis,axis)
angle=lambda a,b:np.degrees(np.arccos(np.clip(np.dot(a,b),-1,1)))
print('Captured first return: prior error',angle(prior,goal))
for f in [.02,.08,.2,.5,.8,1.]:
 rot=Slerp([0,1],R.from_quat([prev[0,3:],idle[0,3:]]))(f)
 hip=prev[0,:3]*(1-f)+idle[0,:3]*f;end=prev[2,:3]*(1-f)+idle[2,:3]*f;a=unit(end-hip)
 legacy=transport(plane(rot.apply(offset),a),a,axis)
 delta=np.arctan2(np.dot(axis,np.cross(prior,goal)),np.dot(prior,goal));coherent=R.from_rotvec(axis*delta*f).apply(prior)
 print('follow',f,'old error',round(angle(legacy,goal),3),'coherent error',round(angle(coherent,goal),3))
