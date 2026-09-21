"""Reproduce the rejected loaded NN-hint solver to locate its discontinuities."""
import json,pathlib,sys,math,numpy as np
from ReplayTemperedLeg import unit,project,rot,points,config,offsets,clean,mixstate
def degdot(a,b):return math.degrees(math.acos(float(np.clip(np.dot(unit(a),unit(b)),-1,1))))
def smooth(x):x=np.clip(x,0,1);return x*x*(3-2*x)
def rotate(v,a,t):return v*math.cos(t)+np.cross(a,v)*math.sin(t)+a*np.dot(a,v)*(1-math.cos(t))
p=pathlib.Path(sys.argv[1]);out=[];last=None;kick=0;was=False
for line in (p/'pipeline.jsonl').open():
 r=json.loads(line)
 if r['actor']!='BP_ProphecyManualPoseAgent_C_1':continue
 if r['attack'] and not was:kick+=1
 was=r['attack']
 if was or not kick or 'tempering' not in r:last=None;continue
 raw=clean(np.array(r['lower_input'][:41])+np.array(r['lower_delta'][:41]))
 if 'walk_delta' in r:raw=mixstate(raw,clean(np.array(r['lower_input'][:41])+np.array(r['walk_delta'][:41])),r['walk_weight'])
 s=np.array(r['published_lower']);pr=np.array(r['previous_lower']);h,k,a,t=points(s);ph,pk,pa,pt=points(pr)
 axis=unit(a-h);d=np.linalg.norm(a-h);u=k-h;L1=np.linalg.norm(offsets[18]);L2=np.linalg.norm(offsets[19]);along=(L1*L1-L2*L2+d*d)/(2*d);rad=math.sqrt(max(0,L1*L1-along*along))
 old=unit(pa-ph);op=project(pk-ph,old);c=np.dot(old,axis);pole=project(-op if c<-1+1e-6 else op-(old+axis)*np.dot(op,axis)/max(1e-6,1+c),axis)
 rawupper=offsets[18]@rot(raw,18);hint=rawupper-axis*np.dot(rawupper,axis);guide=unit(hint) if r['tempering'][1]>0 and np.dot(hint,hint)>1e-10 else pole
 toe=unit(t-a);fw=unit(toe*[1,1,0]);side=np.cross([0,0,1],fw);sa=np.dot(axis,side);n0=side-axis*sa;nl=np.linalg.norm(n0);n=unit(n0);T=unit(np.cross(axis,n));sign=np.dot(guide,T)
 reflect=axis[2]<=0 and sign<0
 if reflect:guide=guide-T*2*sign
 qraw=-along*sa/max(1e-12,rad*nl);q=np.clip(qraw,-1,1);tan=T*math.sqrt(max(0,1-q*q));candidate=n*q+tan;other=n*q-tan
 if np.dot(other,guide)>np.dot(candidate,guide):candidate=other
 w=smooth((1-abs(qraw))*2)*smooth(abs(np.dot(guide,T))*4)
 angle=math.atan2(np.dot(axis,np.cross(guide,candidate)),np.dot(guide,candidate));goal=rotate(guide,axis,angle*w)
 angle2=math.atan2(np.dot(axis,np.cross(pole,goal)),np.dot(pole,goal));final=rotate(pole,axis,angle2*smooth(np.dot(toe*[1,1,0],toe*[1,1,0])*4))
 row=dict(kick=kick,time=r['time'],z=axis[2],hint_radius_cm=np.linalg.norm(hint)*100,hint_sign=sign,reflected=bool(reflect),plane_weight=w,q=qraw,
  source_upper=rawupper.tolist(),axis=axis.tolist(),guide=guide.tolist(),goal=goal.tolist(),foot_heading=fw.tolist(),
  source_step_deg=degdot(pk-ph,u),replay_error_cm=np.linalg.norm(axis*along+final*rad-u)*100)
 if last:
  for key in ('source_upper','axis','guide','goal','foot_heading'):row[key+'_step_deg']=degdot(last[key],row[key])
 out.append(row);last=row
result=dict(capture=p.name,max_replay_error_cm=max(r['replay_error_cm'] for r in out),worst_steps=sorted(out,key=lambda r:r['source_step_deg'],reverse=True)[:8])
(p/'snap-mechanism.json').write_text(json.dumps(dict(summary=result,frames=out),indent=2));print(json.dumps(result,indent=2))
