exec(open('Saved/Diagnostics/ExperimentSidePlane.py').read().split('oldA=')[0])
last=None;worst=0
for i in range(121):
    a=1+i/120;A=np.array([0,math.sin(a),-math.cos(a)]);forward=np.array([1.,0,0])
    guide=unit(forward-(np.array([0,0,-1.])+A)*np.dot(forward,A)/(1-A[2]))
    N=np.array([0,1,0])-A*A[1];nn=np.linalg.norm(N);N=unit(N)
    rawq=-along*A[1]/max(1e-9,radius*nn);q=np.clip(rawq,-1,1);T=unit(np.cross(A,N))*math.sqrt(max(0,1-q*q))
    desired=N*q+T
    if np.dot(N*q-T,guide)>np.dot(desired,guide):desired=N*q-T
    def smooth(t):t=np.clip(t,0,1);return t*t*(3-2*t)
    w=smooth(nn*nn*4)*smooth((1-abs(rawq))*2)*smooth(abs(np.dot(guide,unit(T)))*4)
    angle=math.atan2(np.dot(A,np.cross(guide,desired)),np.dot(guide,desired))
    pole=unit(rotate(guide,A,angle*w));U=A*along+pole*radius
    if last is not None:worst=max(worst,math.acos(np.clip(np.dot(unit(U),unit(last)),-1,1)))
    last=U
print(worst,math.degrees(worst))
