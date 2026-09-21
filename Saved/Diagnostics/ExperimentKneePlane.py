import json,sys,pathlib,math
import numpy as np
from ReplayTemperedLeg import config,offsets,rot,unit,points
p=pathlib.Path(sys.argv[1])
rows=[json.loads(s) for s in (p/'pipeline.jsonl').open()]
for r in rows:
    if r['actor']!='BP_ProphecyManualPoseAgent_C_1' or r['attack']:continue
    if not any(abs(r['time']-t)<.012 for t in (1.68333,2.48333,3.51667,3.55,4.51667,5.55,9.51667)):continue
    s=np.array(r['published_lower']);h,k,a,t=points(s);A=unit(a-h);u=k-h
    toe=unit(t-a);forward=unit(toe*np.array([1,1,0]));side=np.cross([0,0,1],forward)
    footup=np.array([1 if offsets[19][0]<0 else -1,0,0]);localforward=unit(np.array(config['ik_toe_offsets_m'][0]))
    soleSide=unit(np.cross(footup,localforward))@rot(s,12);flatSide=unit(soleSide*np.array([1,1,0]));soleForward=np.cross(flatSide,[0,0,1])
    along=np.dot(u,A);radius=np.linalg.norm(u-A*along);N=side-A*np.dot(side,A);nn=np.linalg.norm(N)
    c=-along*np.dot(A,side)/max(1e-9,radius*nn);n=unit(N);T=unit(np.cross(A,n));q=np.clip(c,-1,1)
    cand=[A*along+radius*(q*n+sgn*math.sqrt(max(0,1-q*q))*T) for sgn in (1,-1)]
    print(json.dumps(dict(time=r['time'],axis=A.tolist(),along=along,radius=radius,plane_cos=c,
        current_side_cm=np.dot(u,side)*100,current_forward_cm=np.dot(u,forward)*100,
        heading_disagreement=math.degrees(math.acos(np.clip(np.dot(soleForward,forward),-1,1))),
        toe_z=toe[2],plane_confidence=nn*nn,soleSide_z=soleSide[2],feet_follow=r.get('tempering'),
        candidates=[dict(side_cm=np.dot(v,side)*100,forward_cm=np.dot(v,forward)*100,up_cm=v[2]*100) for v in cand])))
