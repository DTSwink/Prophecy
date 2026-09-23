import json,sys,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R,Slerp
d=json.loads(Path(sys.argv[1]).read_text());last={};exits={};out={}
def blade(row,mode):
    b=row['bones'];v=lambda n:np.array(b[n][min(mode,1)][:3]);up=v('neck_01')-v('pelvis');up/=np.linalg.norm(up)
    right=v('upperarm_r')-v('upperarm_l');w=np.linalg.norm(right)/2;right-=up*np.dot(up,right);right/=np.linalg.norm(right)
    m=np.stack([np.cross(right,up),right,up]);o=(v('upperarm_r')+v('upperarm_l'))/2
    hand=m@(v('hand_r')-o);q=R.from_matrix(m)*R.from_quat(b['hand_r'][min(mode,1)][3:]);weapon=row['weapon'];g=R.from_quat(weapon['grip'][3:])
    lo=np.array(weapon['min']);hi=np.array(weapon['max']);axis=np.argmax(hi-lo);scale=np.array(weapon['scale']);p0=(lo+hi)*.5;p1=p0.copy();p0[axis]=lo[axis];p1[axis]=hi[axis]
    if mode==2:
        hand=m@(np.array(weapon['actual'][:3])-o);q=R.from_matrix(m)*R.from_quat(weapon['actual'][3:]);p0*=scale;p1*=scale
    else:
        p0=np.array(weapon['grip'][:3])+g.apply(p0*scale);p1=np.array(weapon['grip'][:3])+g.apply(p1*scale)
    return hand,q,p0,p1,w
def score(h,q,p0,p1,w):
    a=h+q.apply(p0);b=h+q.apply(p1);dv=b-a;low,high=0.,1.
    if abs(dv[2])<1e-9:
        if a[2]<-3*w or a[2]>.7*w:return 1e6
    else:
        ts=sorted([(-3*w-a[2])/dv[2],(.7*w-a[2])/dv[2]]);low=max(0.,ts[0]);high=min(1.,ts[1])
        if low>high:return 1e6
    radii=np.array([.9*w+3,w+3]);p=a[:2]/radii;v=dv[:2]/radii;t=np.clip(-np.dot(p,v)/max(1e-12,np.dot(v,v)),low,high)
    return float(np.dot(p+t*v,p+t*v))
for row in d['rows']:
    a=row['agent'];prev=last.get(a);last[a]=row
    if prev and 'ATTACKING' in prev['state'] and 'LOCOMOTION' in row['state']:exits[a]=(row['frame'],prev['attack'])
    if a not in exits or 'LOCOMOTION' not in row['state'] or not row.get('weapon'):continue
    frame,attack=exits[a];key=f'{a}:{frame}';r=out.setdefault(key,{'attack':attack,'future':1e6,'presented':1e6,'actual':1e6,'swept':1e6,'post4_swept':1e6,'min_frame':0})
    for mode,name in [(0,'future'),(1,'presented'),(2,'actual')]:
        h,q,p0,p1,w=blade(row,mode);s=score(h,q,p0,p1,w);r[name]=min(r[name],s)
        if mode==1 and prev and prev.get('weapon'):
            ph,pq,_,_,pw=blade(prev,mode);interp=Slerp([0.,1.],R.from_quat([pq.as_quat(),q.as_quat()]))
            for t in np.linspace(0,1,9):
                s=score(ph+(h-ph)*t,interp(t),p0,p1,pw+(w-pw)*t)
                if s<r['swept']:r['swept']=s;r['min_frame']=row['frame']-frame
                if row['frame']-frame>4:r['post4_swept']=min(r['post4_swept'],s)
print(json.dumps(out,indent=2));Path(sys.argv[1]).with_suffix('.sweep-metrics.json').write_text(json.dumps(out,indent=2))
