import numpy as np,math
def unit(x):return x/max(1e-12,np.linalg.norm(x))
def rotate(v,axis,a):return v*math.cos(a)+np.cross(axis,v)*math.sin(a)+axis*np.dot(axis,v)*(1-math.cos(a))
along=(.45**2-.43**2+.35**2)/(.7);radius=math.sqrt(.45**2-along**2)
oldA=np.array([0,0,-1.]);pole=np.array([1.,0,0]);last=None;worst=(0,None)
for i in range(121):
    a=1+i/120;A=np.array([0,math.sin(a),-math.cos(a)])
    pole=unit(pole-(oldA+A)*np.dot(pole,A)/max(1e-6,1+np.dot(oldA,A)))
    N=np.array([0,1,0])-A*A[1];nn=np.linalg.norm(N);N=unit(N)
    rawq=-along*A[1]/max(1e-9,radius*nn);q=np.clip(rawq,-1,1);T=unit(np.cross(A,N))*math.sqrt(max(0,1-q*q))
    desired=N*q+T
    if A[2]>0 and np.dot(N*q-T,pole)>np.dot(desired,pole):desired=N*q-T
    reliability=np.clip(nn*nn*4,0,1);strength=reliability**2*(3-2*reliability)
    feasible=np.clip((1-abs(rawq))*4,0,1);strength*=feasible**2*(3-2*feasible)
    angle=math.atan2(np.dot(A,np.cross(pole,desired)),np.dot(pole,desired))
    pole=unit(rotate(pole,A,angle*strength));U=A*along+pole*radius
    if last is not None:
        step=math.acos(np.clip(np.dot(unit(U),unit(last)),-1,1))
        if step>worst[0]:worst=(step,dict(i=i,a=a,q=q,strength=strength,angle=angle,upper=U.tolist()))
    last=U;oldA=A
print('worst',worst[0],math.degrees(worst[0]),worst[1])
