import json,pickle,xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial.transform import Rotation as R
from repair_slow_targets import Geometry,P,ROOT
out=ROOT/'Saved/MimicKitSlowLoco/limp-strength-20261101';g=Geometry();xml=ET.parse(P/'assets/uefn/humanoid_uefn.xml');bodies={b.get('name'):b for b in xml.iter('body')}
m=[];offset=[];inertia=[]
for n in g.names:
 b=bodies[n].find('inertial');m.append(float(b.get('mass')));offset.append(np.fromstring(b.get('pos'),sep=' '));rot=R.from_quat(np.fromstring(b.get('quat'),sep=' ')[[1,2,3,0]]).as_matrix();inertia.append(rot@np.diag(np.fromstring(b.get('diaginertia'),sep=' '))@rot.T)
m=np.array(m);offset=np.array(offset);inertia=np.array(inertia);report={'mass_kg':float(sum(m)),'weight_n':float(sum(m)*9.81),'method':'Newton-Euler inverse wrench of bodies above stance joint; assumes only enabled foot external contact, exact authored trajectory; excludes aerodynamic drag and contact/limit impulses. Not a feasibility proof.'}
for motion,side in [('limpL','right'),('limpR','left')]:
 clip=pickle.loads((P/'motions'/(motion+'.pkl')).read_bytes());dt=1/clip['fps'];poses=[g.fk(f) for f in clip['frames']];p=np.array([x[0] for x in poses]);r=np.array([x[1] for x in poses]);combody=p+np.einsum('tbij,bj->tbi',r,offset);com=np.einsum('tbi,b->ti',combody,m)/sum(m);acc=np.gradient(np.gradient(combody,dt,axis=0),dt,axis=0)
 w=np.zeros_like(p);w[1:]=R.from_matrix((r[1:]@r[:-1].transpose(0,1,3,2)).reshape(-1,3,3)).as_rotvec().reshape(-1,15,3)/dt;w[0]=w[1];alpha=np.gradient(w,dt,axis=0);I=r@inertia[None]@r.transpose(0,1,3,2);mom=np.einsum('tbij,tbj->tbi',I,alpha)+np.cross(w,np.einsum('tbij,tbj->tbi',I,w));force=m[None,:,None]*(acc+np.array([0,0,9.81]));net=force.sum(axis=1)
 floors=[]
 for pp,rr in poses:g.set_pose(pp,rr);floors.append(g.floors())
 floors=np.array(floors);fi=g.names.index(side+'_foot');support=floors[:,g.gb==fi].min(axis=1)<.01;otherfi=g.names.index(('left' if side=='right' else 'right')+'_foot');othercontact=floors[:,g.gb==otherfi].min(axis=1)<.01;both=int((support&othercontact).sum());single=int((support&~othercontact).sum());support[:3]=False;support[-3:]=False
 result={'duration_s':(len(p)-1)*dt,'pelvis_height_range_cm':float(np.ptp(p[:,0,2])*100),'com_vertical_range_cm':float(np.ptp(com[:,2])*100),'up_speed_p95_max_m_s':np.percentile(np.gradient(com,dt,axis=0)[3:-3,2],[95,100]).tolist(),'required_ground_force_bw_p50_p95_max':np.percentile(net[support,2]/(sum(m)*9.81),[50,95,100]).tolist(),'support_samples':int(support.sum()),'both_feet_near_floor_samples':both,'enabled_only_near_floor_samples':single,'foot_height_ranges_cm':{side: (floors[:,g.gb==fi].min(axis=1)[[np.argmin(floors[:,g.gb==fi].min(axis=1)),np.argmax(floors[:,g.gb==fi].min(axis=1))]]*100).tolist(),'disabled':(np.array([floors[:,g.gb==otherfi].min(),floors[:,g.gb==otherfi].min(axis=1).max()])*100).tolist()},'joint_torque_demand':{}}
 for part,cap in [('thigh',200),('shin',150),('foot',90)]:
  b=g.names.index(side+'_'+part);exclude=[i for i in range(15) if i==b or (i>=g.names.index(side+'_thigh') and i<=g.names.index(side+'_foot') and i>b)]
  keep=[i for i in range(15) if i not in exclude];torque=(mom[:,keep]+np.cross(combody[:,keep]-p[:,b,None,:],force[:,keep])).sum(axis=1)
  joint=g.k.get_joint(b);axes=r[:,g.parents[b]]@g.lr[b];local=np.einsum('tji,tj->ti',axes,torque)
  if part=='shin':required=abs(local@joint.axis.numpy());ratio=required/cap
  else:required=abs(local).max(axis=1);ratio=required/cap
  result['joint_torque_demand'][part]={'cap_nm_per_axis':cap,'max_axis_nm_p50_p95_max':np.percentile(required[support],[50,95,100]).tolist(),'fraction_stance_over_cap':float((ratio[support]>1).mean())}
 report[motion]=result
(out/'reference-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
