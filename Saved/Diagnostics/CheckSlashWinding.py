import numpy as np
from scipy.spatial.transform import Rotation
def path(p,q,w,t):
    x=.9*w;y=w
    a=np.arctan2(p[1]/y,p[0]/x);b=np.arctan2(q[1]/y,q[0]/x)
    r0=np.hypot(p[0]/x,p[1]/y);r1=max(1.08,np.hypot(q[0]/x,q[1]/y));r=r0+(r1-r0)*t;a=a+(b-a)*t
    return np.array([x*r*np.cos(a),y*r*np.sin(a),p[2]+(q[2]-p[2])*t])
def clearance(h,yaw,w):
    a=h[:2]/[.9*w,w];v=Rotation.from_euler('z',yaw,degrees=True).apply([110.,0,0])[:2]/[.9*w,w]
    t=np.clip(-a@v/(v@v),0,1);return (a+v*t)@(a+v*t)
for start,yaw,end in [(np.array([-20.,-25,-20]),135,np.array([-3.,25,-30])),(np.array([39.,11,-15]),-5,np.array([-3.,25,-30]))]:
    costs=[]
    for goal in [0.,360.,-360.]:
        if abs(goal-yaw)>360:continue
        costs.append((sum(max(0.,1.04-clearance(path(start,end,22,t),yaw+(goal-yaw)*t,20)) for t in np.arange(1,49)/48)+abs(goal-yaw)*1e-5,goal))
    print('start',start,'yaw',yaw,'candidate costs',costs,'selected',min(costs)[1])
    assert min(costs)[1]==(360. if yaw==135 else 0.)
