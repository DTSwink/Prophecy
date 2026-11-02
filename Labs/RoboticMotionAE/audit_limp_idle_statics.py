"""Optimistic static equilibrium test, actual masses/joint coordinates, no rollout changes."""
import json,pickle,itertools,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np,mujoco
from scipy.spatial.transform import Rotation as R
from scipy.optimize import linprog
from repair_slow_targets import Geometry,P,ROOT
out=ROOT/'Saved/MimicKitSlowLoco/idle-asymmetry-audit-20261101';g=Geometry();xml=ET.parse(P/'assets/uefn/humanoid_uefn.xml');xr=xml.getroot()
for b in xr.findall('.//body'):
 joints=b.findall('joint')
 if len(joints)==3:
  for j in joints:b.remove(j)
  ET.SubElement(b,'joint',name=b.get('name')+'_ball',type='ball',limited='false',stiffness='0',damping='0',armature='0')
for tag in ['actuator','sensor','keyframe']:
 for element in xr.findall(tag):xr.remove(element)
m=mujoco.MjModel.from_xml_string(ET.tostring(xr,encoding='unicode'));m.dof_armature[:]=0;m.dof_damping[:]=0;d=mujoco.MjData(m)
controller=json.loads((P/'prepared/env_config.yaml').read_text()) if False else None
caps=np.array([200]*3+[50]*3+[100]*3+[70]+[50]*3+[100]*3+[70]+[50]*3+[400]*3+[500]+[180]*3+[400]*3+[500]+[180]*3,float)
results={}
for name,active,passive in [('limpL_idle',11,14),('limpR_idle',14,11)]:
 fr=pickle.loads((P/'motions'/(name+'.pkl')).read_bytes())['frames'];rows=[]
 for t in range(0,len(fr)-1,120):
  f=fr[t];pp,rr=g.fk(f);g.set_pose(pp,rr);d.qpos[:3]=f[:3];d.qpos[3:7]=R.from_rotvec(f[3:6]).as_quat()[[3,0,1,2]]
  for b in range(1,15):
   j=g.k.get_joint(b);a=m.jnt_qposadr[b];v=f[6+j.dof_idx:6+j.dof_idx+j.get_dof_dim()]
   if len(v)==3:d.qpos[a:a+4]=R.from_rotvec(v).as_quat()[[3,0,1,2]]
   else:d.qpos[a]=v[0]
  d.qvel[:]=0;mujoco.mj_forward(m,d);np.testing.assert_allclose(d.xpos[1:],pp,atol=1e-5)
  demand=d.qfrc_bias.copy();passivedofs=np.arange(g.k.get_joint(passive-2).dof_idx,g.k.get_joint(passive).dof_idx+3)
  solutions={}
  for mode in ['active_foot_only','both_feet','both_powered']:
   js=[]
   for b in ([active] if mode=='active_foot_only' else [active,passive]):
    gi=np.flatnonzero(g.gb==b)[0];sz=np.array(g.gs[gi]['size']);center=pp[b]+rr[b]@g.gp[gi];gr=rr[b]@g.gr[gi];corners=center+np.array(list(itertools.product([-1,1],repeat=3)))*sz@gr.T
    # Lower face / near-lowest corners only, translated down by the small authored ground gap.
    corners=corners[corners[:,2]<=corners[:,2].min()+.005]
    for point in corners:
     jac=np.zeros((3,40));mujoco.mj_jac(m,d,jac,None,point,b+1);js.append(jac.T)
   J=np.concatenate(js,axis=1);nf=J.shape[1];A=np.c_[J,np.eye(40)[:,6:]];cc=caps.copy()
   if mode!='both_powered':cc[passivedofs]=0
   B=[]
   for k in range(nf//3):
    for axis in (0,1):
     for sign in [-1,1]:
      b=np.zeros(nf+34);b[3*k+axis]=sign;b[3*k+2]=-0.8;B.append(b)
   aa=np.c_[A,np.eye(40),-np.eye(40)];ub=np.c_[np.array(B),np.zeros((len(B),80))]
   opt=linprog(np.r_[np.zeros(nf+34),np.ones(80)],A_ub=ub,b_ub=np.zeros(len(B)),A_eq=aa,b_eq=demand,bounds=[(None,None),(None,None),(0,None)]*(nf//3)+[(-v,v) for v in cc]+[(0,None)]*80,method='highs');assert opt.success
   residual=A@opt.x[:nf+34]-demand
   solutions[mode]=dict(residual_l1=float(opt.fun),passive_residual_nm=np.abs(residual[6+passivedofs]).tolist(),torque_nm=opt.x[nf:nf+34].tolist())
  rows.append(dict(frame=t,solutions=solutions))
 results[name]=dict(samples=rows,summary={mode:dict(residual_mean=float(np.mean([r['solutions'][mode]['residual_l1'] for r in rows])),residual_max=float(max(r['solutions'][mode]['residual_l1'] for r in rows))) for mode in solutions})
(out/'statics-report.json').write_text(json.dumps(dict(method='Optimistic static equilibrium with freely chosen friction-limited foot contact forces; omits acceleration, passive joint-limit reactions, motor-speed and contact solver details. Feasibility is not dynamic tracking proof.',motions=results),indent=2))
print(json.dumps({n:r['summary'] for n,r in results.items()},indent=2))
