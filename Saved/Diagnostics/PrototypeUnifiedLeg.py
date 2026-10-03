import json,pathlib,math,numpy as np
from scipy.spatial.transform import Rotation
from ReplayTemperedLeg import unit,project,rot,mixrot,clean
p=pathlib.Path(__file__).resolve().parents[2];d=p/'Saved/Diagnostics'
c=json.loads((p/'Content/locomotion/NN/prophecy_lower_body_runtime.json').read_text())
w=json.loads((p/'Content/locomotion/NN/prophecy_lower_body_walk_july5_runtime.json').read_text())
off=np.array(c['local_offsets_m']);box=c['foot_roll']
def smooth(v):v=np.clip(v,0,1);return v*v*(3-2*v)
def turn(a,t):return Rotation.from_rotvec(a*t).as_matrix().T
def angle(a,b):return math.degrees(Rotation.from_matrix(a@b.T).magnitude())
def minimum(s,i):
 o=9+16*i;r=rot(s,o+3);f=r[1].copy();up=r[0].copy();side=r[2]
 tv=np.array(w['ik_toe_offsets_m'][i])@r
 if np.dot(f,tv)<0:f=-f
 if up[2]<0:up=-up
 fh=np.array(box['foot_half_dims_m']);th=np.array(box['toe_half_dims_m']);sole=box['sole_vertical_offset_m']
 fc=tv-f*fh[0]+up*sole
 tr=turn(np.array(w['ik_toe_axes'][i]),s[o+15]*w['ik_toe_alpha_rad'])@r
 tf=tr[0].copy();tu=tr[1].copy();ts=tr[2]
 if np.dot(tf,tv)<0:tf=-tf
 if tu[2]<0:tu=-tu
 tc=tv+tf*th[0]+tu*sole
 return -min(fc[2]-np.dot(np.abs([f[2],side[2],up[2]]),fh),tc[2]-np.dot(np.abs([tf[2],ts[2],tu[2]]),th))+1e-5
def evaluate(row,i):
 prev=np.array(row['previous_lower']);nn=clean(np.array(row['lower_input'][:41])+row['lower_delta'][:41]);target=np.array(row['published_lower'])
 o=9+16*i;ho=off[17+4*i];ko=off[18+4*i];local=unit(np.array(w['ik_toe_offsets_m'][i]))
 def hip(s):return s[:3]+ho@rot(s,3)
 H=hip(target);axis=unit(target[o:o+3]-H);L1=np.linalg.norm(ko)
 L2=np.linalg.norm(target[o:o+3]-H-ko@rot(target,o+9))
 def solve(s):
  ou=ko@rot(s,o+9);oa=unit(s[o:o+3]-hip(s));op=project(ou,oa)
  pole=project(op-(oa+axis)*np.dot(op,axis)/max(1e-6,1+np.dot(oa,axis)),axis)
  dist=min(np.linalg.norm(target[o:o+3]-H),L1+L2-2e-5);along=(L1*L1-L2*L2+dist*dist)/(2*dist)
  upper=axis*along+pole*np.sqrt(max(0,L1*L1-along*along));on=unit(np.cross(oa,op));n=unit(np.cross(axis,pole))
  ob=np.array([unit(ou),unit(np.cross(on,unit(ou))),on]);nb=np.array([unit(upper),unit(np.cross(n,unit(upper))),n])
  return rot(s,o+9)@ob.T@nb,pole
 toe=local@rot(target,o+3);f=unit(toe*[1,1,0]);side=np.cross([0,0,1],f)
 st=local@rot(nn,o+3);sf=unit(st*[1,1,0]);yaw=math.atan2(np.cross(sf,f)[2],np.dot(sf,f));T=turn(np.array([0,0,1]),yaw)
 src=nn.copy();src[o:o+3]=hip(src)+(src[o:o+3]-hip(src))@T
 for z in (o+3,o+9):src[z:z+6]=(rot(src,z)@T)[:2].ravel()
 follow=row['tempering'][1] if i==0 else row['right_foot_tempering'][2]
 support=1-smooth((target[o+2]-minimum(target,i)-.02)/.10)
 diff=math.radians(angle(rot(prev,o+9),rot(src,o+9)))
 weight=follow*support*smooth(np.linalg.norm(st*[1,1,0])**2*4)*smooth(np.linalg.norm(toe*[1,1,0])**2*4)*min(1,math.radians(20)/max(diff,1e-6))
 aligned_prev=prev.copy();pt=local@rot(prev,o+3);pf=unit(pt*[1,1,0]);py=math.atan2(np.cross(pf,f)[2],np.dot(pf,f));ptu=turn(np.array([0,0,1]),py)
 aligned_prev[o:o+3]=hip(prev)+(prev[o:o+3]-hip(prev))@ptu
 for z in (o+3,o+9):aligned_prev[z:z+6]=(rot(prev,z)@ptu)[:2].ravel()
 r0,p0=solve(aligned_prev);r1,p1=solve(src);cos=np.clip(np.dot(p0,p1),-1,1);sa=unit(src[o:o+3]-hip(src));su=ko@rot(src,o+9)
 weight*=smooth(np.linalg.norm(su-sa*np.dot(su,sa))/(L1*.02))*smooth((1+cos)/.02)*smooth((1+np.dot(sa,axis))/.05)
 bend=math.atan2(np.dot(axis,np.cross(p0,p1)),cos)
 thigh=mixrot(r0@turn(axis,bend*weight),r1@turn(axis,-bend*(1-weight)),weight)
 upper=ko@thigh;along=np.dot(upper,axis);radial=upper-axis*along;radius=np.linalg.norm(radial);pole=unit(radial)
 sidealong=np.dot(axis,side);n0=side-axis*sidealong;nl=np.linalg.norm(n0);N=unit(n0);hp=unit(np.cross(axis,N));transported=np.dot(upper,side)
 def lateral(s):
  t=local@rot(s,o+3);ff=unit(t*[1,1,0]);val=np.dot(ko@rot(s,o+9),np.cross([0,0,1],ff));conf=smooth(np.linalg.norm(t*[1,1,0])**2*4)
  return transported*(1-conf)+val*conf
 desired=lateral(prev)*(1-weight)+lateral(src)*weight;q=(desired-along*sidealong)/max(1e-9,radius*nl);branch=np.dot(pole,hp)
 strength=follow*smooth(np.linalg.norm(toe*[1,1,0])**2*4)*smooth(nl*nl*4)*smooth((1-abs(q))*4)*smooth(abs(branch)*4)
 cq=np.clip(q,-1,1);dp=N*cq+hp*np.sign(branch)*np.sqrt(max(0,1-cq*cq));plane=math.atan2(np.dot(axis,np.cross(pole,dp)),np.clip(np.dot(pole,dp),-1,1))
 out=thigh
 return dict(t=row['time'],side=i,step=angle(rot(prev,o+9),out),source_follow=float(weight),radius_cm=radius*100,Q=q,
  plane_strength=float(strength),plane_turn_deg=math.degrees(plane*strength),source_bend_deg=math.degrees(bend*weight),
  error_deg=angle(out,rot(target,o+9)),length_cm=L2*100,plane_thigh=out[:2].ravel().tolist(),transported_thigh=thigh[:2].ravel().tolist(), hinge_forward=float(np.dot(pole,hp)), knee_side_cm=float(np.dot(ko@out,side)*100))

rows=[r for r in map(json.loads,(d/'FootVibration-nn-pelvis159-baseline.jsonl').read_text().splitlines()) if r['actor'].endswith('_C_1') and not r['attack'] and r.get('tempering')]
out=[evaluate(r,i) for r in rows for i in (0,1)]
(d/'Pelvis159-unified-fixed-input.json').write_text(json.dumps(out,indent=2))
for v in out:
 if 149<=round(v['t']*60)<=159:print({k:round(x,4) if isinstance(x,float) else x for k,x in v.items() if k in ('t','side','step','hinge_forward','knee_side_cm')})
print('samples',len(out),'backward',sum(v['hinge_forward']<0 for v in out))
