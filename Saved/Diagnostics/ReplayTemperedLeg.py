import json,sys,pathlib,math
import numpy as np
from scipy.spatial.transform import Rotation,Slerp
ROOT=pathlib.Path(__file__).resolve().parents[2]
config=json.loads((ROOT/'Content/locomotion/NN/prophecy_lower_body_runtime.json').read_text())
offsets=np.array(config['local_offsets_m'])
def unit(v):return v/max(1e-12,np.linalg.norm(v))
def project(v,a):return unit(v-a*np.dot(v,a))
def rot(s,o):
    a=unit(np.array(s[o:o+3])); b=project(np.array(s[o+3:o+6]),a)
    return np.array([a,b,np.cross(a,b)])
def mixrot(a,b,w):return Slerp([0,1],Rotation.from_matrix([a.T,b.T]))([w]).as_matrix()[0].T
def clean(s):
    s=np.array(s).copy()
    for o in [3,12,18,28,34]:s[o:o+6]=rot(s,o)[:2].ravel()
    s[[24,40]]=np.clip(s[[24,40]],-1,1)
    return s
def mixstate(a,b,w):
    c=a*(1-w)+b*w
    for o in [3,12,18,28,34]:c[o:o+6]=mixrot(rot(a,o),rot(b,o),w)[:2].ravel()
    return c
def points(s,i=0):
    h=s[:3]+offsets[17+4*i]@rot(s,3);u=offsets[18+4*i]@rot(s,18+16*i)
    a=s[9+16*i:12+16*i];f=np.array(config['ik_toe_offsets_m'][i])@rot(s,12+16*i)
    return h,h+u,a,a+f
def info(s):
    h,k,a,t=points(s);u=k-h;axis=unit(a-h);f=unit(t-a);bend=u-axis*np.dot(u,axis)
    flat=unit(f*np.array([1,1,0]));right=np.cross([0,0,1],flat)
    return dict(yaw=math.degrees(math.atan2(np.dot(u,right),np.dot(u,flat))),
        bend_cm=np.linalg.norm(bend)*100,knee=np.round(k*100,2).tolist(),
        pole=unit(bend).tolist(),axis=axis.tolist(),footforward=f.tolist(),
        calf_cm=np.linalg.norm(a-k)*100)
def transport(source,target):
    h,k,a,_=points(source);H,K,A,T=points(target)
    old=unit(a-h);new=unit(A-H);p=project(k-h,old)
    change=rot(source,12).T@rot(target,12)
    old=unit(old@change);p=project(p@change,old)
    c=np.dot(old,new)
    pole=project(-p if c < -1+1e-6 else p-(old+new)*np.dot(p,new)/max(1e-6,1+c),new)
    forward=project(T-A,new)
    return dict(swing=math.degrees(math.acos(np.clip(c,-1,1))),polefoot=math.degrees(math.acos(np.clip(np.dot(pole,forward),-1,1))))
if __name__=='__main__':
    p=pathlib.Path(sys.argv[1]);rows=[json.loads(l) for l in (p/'pipeline.jsonl').open()]
    out=[]
    for r in rows:
        if r['actor']!='BP_ProphecyManualPoseAgent_C_1' or r['attack']:continue
        raw=clean(np.array(r['lower_input'][:41])+np.array(r['lower_delta'][:41]));walk=None
        if 'walk_delta' in r:
            walk=clean(np.array(r['lower_input'][:41])+np.array(r['walk_delta'][:41]));raw=mixstate(raw,walk,r['walk_weight'])
        pub=np.array(r['published_lower']);prev=np.array(r['previous_lower'])
        out.append(dict(time=r['time'],w=r['walk_weight'],settings=r.get('tempering'),
            raw=info(raw),published=info(pub),previous=info(prev),transport=transport(raw,pub),raw_state=raw.tolist(),published_state=pub.tolist(),previous_state=prev.tolist()))
    (p/'replay.json').write_text(json.dumps(out))
    for r in out:
        if 3.3<r['time']<4.0 or 8.3<r['time']<8.75:
            print(json.dumps({k:({q:round(v,2) if isinstance(v,float) else v for q,v in val.items() if q in ['yaw','bend_cm','calf_cm']} if k in ['raw','published','previous'] else val) for k,val in r.items() if not k.endswith('_state')}))
