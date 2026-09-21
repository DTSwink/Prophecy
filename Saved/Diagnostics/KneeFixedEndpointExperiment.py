"""Freeze a recorded hip/ankle/foot and isolate reconstruction-only drift."""
import json,pathlib,math,numpy as np
from ReplayTemperedLeg import points,rot,unit,project,offsets,config
from KneeMechanismAudit import rotate
p=pathlib.Path(__file__).parent/'ThighOutward-20260920-170452'
rows=[json.loads(l) for l in (p/'pipeline.jsonl').open()]
r=min((r for r in rows if r['actor']=='BP_ProphecyManualPoseAgent_C_1' and not r['attack']),key=lambda r:abs(r['time']-3.516666457056999))
s=np.array(r['published_lower']);h,k,a,t=points(s);axis=unit(a-h);d=np.linalg.norm(a-h);L1=np.linalg.norm(offsets[18]);L2=np.linalg.norm(offsets[19]);along=(L1*L1-L2*L2+d*d)/(2*d);radius=math.sqrt(L1*L1-along*along)
fw=unit((t-a)*[1,1,0]);side=np.cross([0,0,1],fw);N=side-axis*np.dot(side,axis);q=-along*np.dot(axis,side)/(radius*np.linalg.norm(N));assert abs(q)<1
n=unit(N);T=unit(np.cross(axis,n));ps=[n*q+v*T*math.sqrt(1-q*q) for v in (1,-1)];pole=max(ps,key=lambda x:np.dot(x,project(k-h,axis)))
up=np.array([1 if offsets[19][0]<0 else -1,0,0]);sole=unit(np.cross(up,unit(config['ik_toe_offsets_m'][0])))@rot(s,12);flat=sole*[1,1,0];f=unit(np.array([flat[1],-flat[0],0]));den=1-axis[2]
guide=project(f-(np.array([0,0,-1])+axis)*np.dot(f,axis)/den,axis);rel=np.clip(den*4,0,1);strength=r['tempering'][1]*np.dot(flat,flat)*rel*rel*(3-2*rel)
result=[]
for i in range(31):
 u=axis*along+pole*radius
 if i in (0,1,2,5,10,30):result.append(dict(solve=i,side_cm=float(np.dot(u,side)*100),forward_cm=float(np.dot(u,fw)*100),hinge_sign=float(np.dot(pole,T)),thigh_cm=float(np.linalg.norm(u)*100),calf_cm=float(np.linalg.norm(a-h-u)*100)))
 angle=math.atan2(np.dot(axis,np.cross(pole,guide)),np.dot(pole,guide));pole=rotate(pole,axis,angle*strength)
out=dict(source_time=r['time'],fixed_hip=h.tolist(),fixed_ankle=a.tolist(),foot_forward=fw.tolist(),ankle_forward_cm=float(np.dot(a-h,fw)*100),plane_candidates=[dict(upper_cm=((axis*along+x*radius)*100).tolist(),forward_cm=float(np.dot(axis*along+x*radius,fw)*100),hinge_sign=float(np.dot(x,T))) for x in ps],tempering=r['tempering'],steps=result)
(p/'fixed-endpoint-experiment.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
