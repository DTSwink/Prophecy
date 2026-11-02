"""Read-only latest replay and approved-target asymmetry audit; CPU only."""
import json,pickle,itertools,xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial.transform import Rotation as R
from scipy.spatial import ConvexHull
from repair_slow_targets import Geometry,P,ROOT
OUT=ROOT/'Saved/MimicKitSlowLoco/idle-asymmetry-audit-20261101'
g=Geometry();xml=ET.parse(P/'assets/uefn/humanoid_uefn.xml');bodies={b.get('name'):b for b in xml.iter('body')}
mass=np.array([float(bodies[n].find('inertial').get('mass')) for n in g.names]);off=np.array([np.fromstring(bodies[n].find('inertial').get('pos'),sep=' ') for n in g.names])
def com(p,r):return ((p+np.einsum('...bij,bj->...bi',r,off))*mass[:,None]).sum(-2)/mass.sum()
def feet(p,r,b):
 gi=np.flatnonzero(g.gb==b)[0];center=p[:,b]+np.einsum('tij,j->ti',r[:,b],g.gp[gi]);rr=r[:,b]@g.gr[gi]
 corners=np.array(list(itertools.product([-1,1],repeat=3)))*g.gs[gi]['size']
 pts=center[:,None]+np.einsum('tij,cj->tci',rr,corners)
 return center,pts,pts[:,:,2].min(-1)
def margin(c,pts):
 out=[]
 for cm,points in zip(c,pts):
  eq=ConvexHull(points[:,:2]).equations;out.append(float(np.min(-(eq[:,:2]@cm[:2]+eq[:,2]))))
 return np.array(out)
def stats(x):return dict(mean=float(np.mean(x)),p05=float(np.percentile(x,5)),p95=float(np.percentile(x,95)),min=float(np.min(x)),max=float(np.max(x)))
def arms_target(p,r,tp,tr):
 pp=p.copy();rr=r.copy()
 for b in range(3,9):
  par=g.parents[b];local=np.einsum('tji,tjk->tik',tr[:,par],tr[:,b]);pp[:,b]=pp[:,par]+np.einsum('tij,j->ti',rr[:,par],g.lp[b]);rr[:,b]=rr[:,par]@local
 return pp,rr
report={};series={}
with np.load(OUT/'latest-replay.npz') as z:
 meta=json.loads(str(z['metadata']));step=meta['iteration']
 for i,name,active,passive in [(8,'limpL_idle',11,14),(9,'limpR_idle',14,11)]:
  row=meta['replay_rows'][i];pose=z['pose_'+str(i)].astype(float);target=z['reference_pose_'+str(i)].astype(float);vel=z['world_velocities_'+str(i)].astype(float);terms=z['loss_terms_'+str(i)]
  p=pose[:,:,:3];r=R.from_quat(pose[:,:,3:].reshape(-1,4)).as_matrix().reshape(-1,15,3,3);tp=target[:,:,:3];tr=R.from_quat(target[:,:,3:].reshape(-1,4)).as_matrix().reshape(-1,15,3,3)
  cm=com(p,r);tcm=com(tp,tr);fc,pts,h=feet(p,r,active);pfc,ppts,ph=feet(p,r,passive);tfc,tpts,th=feet(tp,tr,active)
  ap,ar=arms_target(p,r,tp,tr);acm=com(ap,ar)
  ang=np.rad2deg(R.from_matrix((r.transpose(0,1,3,2)@tr).reshape(-1,3,3)).magnitude().reshape(-1,15));err=np.linalg.norm(p-tp,axis=-1)*100
  poscost=(p-tp).square() if False else ((p-tp)**2).sum(-1)/45*row['loss_weights']['position_mse']
  rotcost=8*np.sin(np.deg2rad(ang)/2)**2/135*row['loss_weights']['rotation_mse']
  enabled=np.ones(15);enabled[passive-2:passive+1]=0
  costs=(poscost+rotcost)*enabled[None]
  after=slice(90,None)
  perbody={n:dict(position_error_cm=stats(err[after,b]),rotation_error_deg=stats(ang[after,b]),pose_loss_mean=float(costs[after,b].mean())) for b,n in enumerate(g.names)}
  m=margin(cm,pts);am=margin(acm,pts);tm=margin(tcm,tpts)
  bodycom=p+np.einsum('tbij,bj->tbi',r,off);targetbodycom=tp+np.einsum('tbij,bj->tbi',tr,off)
  contribution=(bodycom-targetbodycom)*mass[None,:,None]/mass.sum()*100
  report[name]=dict(frames=len(p),terminal=row['terminal_flag'],mean_loss=float(terms[1:,:5].sum(-1).mean()),settled_mean_loss=float(terms[after,:5].sum(-1).mean()),bodies=perbody,
   support_margin_cm=stats(m[after]*100),support_margin_if_target_arms_cm=stats(am[after]*100),target_support_margin_cm=stats(tm*100),
   com_shift_if_target_arms_cm=stats(np.linalg.norm(acm[after,:2]-cm[after,:2],axis=-1)*100),
   arm_com_shift_vector_cm=((acm-cm)[after]*100).mean(0).tolist(),
   active_foot_floor_cm=stats(h[after]*100),passive_foot_floor_cm=stats(ph[after]*100),
   actual_com_minus_support_xy_cm=((cm-fc)[after,:2]*100).mean(0).tolist(),
   active_speed_m_s=stats(np.linalg.norm(vel[after,active,:3],axis=-1)),
   limb_flags=row['limb_enabled'],loss_weights=row['loss_weights'],
   body_com_error_contributions_cm={n:contribution[after,b].mean(0).tolist() for b,n in enumerate(g.names)})
  series[name]=dict(p=p,r=r,tp=tp,tr=tr,com=cm,target_com=tcm,foot=fc,foot_points=pts,margin=m,arms_margin=am,arms_com=acm,terms=terms,hand_error=err[:,[5,8]])
  np.savez_compressed(OUT/(name+'-metrics.npz'),**series[name])
  clip=pickle.loads((P/'motions'/(name+'.pkl')).read_bytes());frames=clip['frames'][::20];lim={};floors=[]
  for f in frames:
   pp,rr=g.fk(f);g.set_pose(pp,rr);floors.append(g.floors());v=g.limits(f)
   for n,bad in v.items():lim[n]=lim.get(n,0)+int(bad)
  report[name]['target_limits_violations']={n:v for n,v in lim.items() if v}
  report[name]['target_min_floor_by_body_cm']={n:float(np.array(floors)[:,g.gb==b].min()*100) for b,n in enumerate(g.names)}
report=dict(checkpoint=step,scope='One deterministic 10s rollout each; settled metrics frames90-300; geometric support margins are not contact-force measurements. Arms counterfactual is instantaneous kinematic mass shift, not a simulated intervention.',motions=report)
(OUT/'balance-report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({n:{k:v for k,v in x.items() if k not in ['bodies','body_com_error_contributions_cm','loss_weights']} for n,x in report['motions'].items()},indent=2))
print('TOP ERRORS',json.dumps({n:sorted([(b,v['pose_loss_mean'],v['position_error_cm']['mean'],v['rotation_error_deg']['mean']) for b,v in x['bodies'].items()],key=lambda a:-a[1])[:7] for n,x in report['motions'].items()}))
