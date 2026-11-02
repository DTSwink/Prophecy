"""Motion-aware, offline PHAT floor/contact repair. Never edits the live package.

Root orientation/XY and head coordinates are retained. Each limb is solved
as its actual seven-DOF chain, with fixed end-effector XY, an explicit support
height, and floor constraints for every collider in the chain. No bone scaling.
"""
import argparse, hashlib, json, pickle, time
import sys
import numpy as np
from scipy.optimize import minimize
from scipy.ndimage import gaussian_filter1d
from scipy.spatial.transform import Rotation as R, Slerp
from repair_slow_targets import Geometry, P, ROOT, coords
sys.path.insert(0,str(ROOT/'Tools/Locomotion'))
from RetargetFootLift import solve_leg

OUT=ROOT/'Saved/MimicKitSlowLoco/contact-cleanup-20261031'
NAMES=['crawl','crawl_idle','agonising','agonising_idle','limpL','limpR','lying','sitting']
C=.0015
DESCRIPTIONS={
 'crawl':'Alternating palm and knee supports; reaching hands keep their swing clearance. Pelvis height clears the knee supports and a small spine adjustment brings the palms within reach; toes cannot pass through the floor.',
 'crawl_idle':'Both palms and knees support the body. Pelvis raised to clear the knee capsules and spine inclined forward to reach the palms, avoiding an artificial wide-knee stance.',
 'agonising':'Supine wounded motion: back/pelvis support and planted feet. Hands stay over the abdomen rather than being forced to the floor.',
 'agonising_idle':'Reclining wounded idle: back support, resting arms and planted feet. Cleared the back and arms independently instead of lifting every support into the air.',
 'limpL':'Left leg remains the passive dragging leg. Right support foot plants during stance and clears its entire collider during the original swing; upper body unchanged.',
 'limpR':'Right leg remains the passive dragging leg. Left support foot plants during stance and clears its entire collider during the original swing; upper body unchanged.',
 'lying':'Reclining on the pelvis and arms: pelvis cleared, hand supports raised to the floor, heel/foot supports retained. Original torso lean retained.',
 'sitting':'User-saved crossed-leg pose: small pelvis lift clears the seat; feet remain on the floor. Hand contacts follow the same points on the legs; torso lean and crossed-leg arrangement retained.'}

def sample(g,frames):
 ps=[];rs=[];bs=[]
 for f in frames:
  p,r=g.fk(f);g.set_pose(p,r);ps.append(p);rs.append(r);bs.append(g.floors())
 return np.array(ps),np.array(rs),np.array(bs)

def interpolate(g,frames,factor):
 t=np.arange(len(frames));u=np.linspace(0,len(frames)-1,(len(frames)-1)*factor+1)
 out=np.stack([np.interp(u,t,frames[:,i]) for i in range(40)],axis=1)
 for sl in [slice(3,6)]+[slice(6+j.dof_idx,9+j.dof_idx) for j in g.joints if j.get_dof_dim()==3]:
  out[:,sl]=Slerp(t,R.from_rotvec(frames[:,sl]))(u).as_rotvec()
 return out

def margins(g,f,bodies):
 values=[]
 for meta in g.meta['joints']:
  body=g.names.index(meta['body'])
  if body not in bodies:continue
  j=g.k.get_joint(body);v=f[6+j.dof_idx:6+j.dof_idx+j.get_dof_dim()]
  if len(v)==1:values.extend([v[0]-meta['range_rad'][0],meta['range_rad'][1]-v[0]])
  else:
   q=(R.from_quat(np.array(meta['reference_wxyz'])[[1,2,3,0]])*R.from_rotvec(v)).as_quat()[[3,0,1,2]]
   c=coords(q);lim=meta['limits_rad'];values.extend([lim[0]-c[0],lim[0]+c[0],1-(c[1]/np.sin(lim[1]/2))**2-(c[2]/np.sin(lim[2]/2))**2])
 return np.array(values)

def plan(g,name,frames):
 ps,rs,bs=sample(g,frames);bottom=lambda b:bs[:,g.gb==b].min(1)
 target={11:np.full(len(frames),C),14:np.full(len(frames),C)}
 root=np.zeros(len(frames))
 if name in ('crawl','crawl_idle'):
  for hand in [5,8]:
   if name=='crawl_idle':h=np.zeros(len(frames))
   else:
    # Inspected authored hand reach phases, expressed in normalized cycle time.
    # Contact phases are determined by planted wrist height and horizontal speed;
    # the authored wrist lift sets the peak, not an invented fixed step height.
    phase=np.arange(len(frames))/(len(frames)-1)
    lo,hi=(14/54,36/54) if hand==5 else (43/54,65/54)
    progress=(phase-lo)%1;dur=hi-lo
    envelope=np.where(progress<dur,np.sin(np.pi*np.minimum(progress/dur,1))**2,0)
    planted=envelope<.01
    amplitude=max(0,float(ps[:,hand,2].max()-np.median(ps[planted,hand,2])))
    h=envelope*amplitude
   target[hand]=h+C
   upper=hand-2;middle=hand-1
   length=np.linalg.norm(g.lp[middle])+np.linalg.norm(g.lp[hand])-.005
   wrist=ps[:,hand].copy();wrist[:,2]+=target[hand]-bottom(hand)
   dxy=np.linalg.norm(wrist[:,:2]-ps[:,upper,:2],axis=1)
   reachable=wrist[:,2]+np.sqrt(np.maximum(.001,length**2-dxy**2))-ps[:,upper,2]
   root=np.minimum(root,reachable)
  # Lowering the pelvis enough to reach the hands forces nearly vertical thighs
  # into a wide frog stance. Preserve the knee-support posture instead and solve
  # the small torso inclination needed for palm reach.
  root=np.maximum(0,C-bs[:,np.isin(g.gb,[9,10,12,13])].min(1))
 elif name.startswith('limp'):
  active=11 if name=='limpL' else 14
  # Recover authored swing clearance from ankle height, rather than the already
  # penetrating toe corner. During the flat stance this is exactly floor contact.
  ankle=ps[:,active,2];baseline=np.median(ankle[ankle<np.quantile(ankle,.6)])
  lift=np.maximum(0,ankle-baseline-.001)
  target[active]=C+lift
 else:
  core=bs[:,np.isin(g.gb,[0,1,2])].min(1)
  root=np.maximum(0,C-core)
  if name in ('agonising_idle','lying'):
   target[5]=np.full(len(frames),C);target[8]=np.full(len(frames),C)
 return ps,rs,bs,root,target

def reachable_torso(g,f,original,ps,rs,bs,targets,i):
 x0=np.r_[original[6:9],f[2]];tips=[];baseheight=f[2];oldmargin=np.minimum(0,margins(g,original,[1]))
 for hand in [5,8]:
  target=ps[hand].copy();target[2]+=targets[hand][i]-bs[g.gb==hand].min();tips.append(target)
 def calc(x):
  ff=f.copy();ff[6:9]=x[:3];ff[2]=x[3];p,r=g.fk(ff);g.set_pose(p,r)
  cost=np.sum((r[1:9]-rs[1:9])**2)+30*np.sum((p[1:9]-ps[1:9]-[0,0,f[2]-original[2]])**2)+3000*(x[3]-baseheight)**2
  cons=[np.linalg.norm(g.lp[h-1])+np.linalg.norm(g.lp[h])-.004-np.linalg.norm(p[h-2]-t) for h,t in zip([5,8],tips)]
  return cost,np.r_[cons,g.floors()[np.isin(g.gb,[0,1,2])]-C,margins(g,ff,[1])-oldmargin]
 result=minimize(lambda x:calc(x)[0],x0,method='SLSQP',bounds=[(v-.6,v+.6) for v in x0[:3]]+[(baseheight-.05,baseheight+.01)],constraints=[dict(type='ineq',fun=lambda x:calc(x)[1])],options=dict(maxiter=100,ftol=1e-10))
 if min(calc(result.x)[1])<-.00001:raise RuntimeError(('unreachable palms',i,result.message))
 f[6:9]=result.x[:3];f[2]=result.x[3];return f

def chain(g,frame,original,upper,desired_bottom,target_xy,knee_target,ref_rot,previous=None):
 bodies=np.arange(upper,upper+3);end=upper+2
 ids=np.concatenate([np.arange(6+g.k.get_joint(int(b)).dof_idx,6+g.k.get_joint(int(b)).dof_idx+g.k.get_joint(int(b)).get_dof_dim()) for b in bodies])
 geom=np.flatnonzero(np.isin(g.gb,bodies[:-1]));endgeom=np.flatnonzero(g.gb==end)
 start=frame[ids].copy();ref=original[ids].copy();cache={}
 p0,r0=g.fk(frame);g.set_pose(p0,r0);target=p0[end].copy();target[:2]=target_xy;target[2]+=desired_bottom-g.floors()[endgeom].min()
 try:
  mid=upper+1;hj,mj,ej=[g.k.get_joint(b) for b in bodies]
  ur,angle,mr,kp=solve_leg(p0[upper],p0[mid],p0[end],target,g.lp[mid],g.lp[end],g.lr[mid],mj.axis.numpy(),frame[6+mj.dof_idx])
  start[:3]=R.from_matrix(g.lr[upper].T@r0[g.parents[upper]].T@ur).as_rotvec();start[3]=angle
  start[4:]=R.from_matrix(g.lr[end].T@mr.T@r0[end]).as_rotvec()
 except ValueError:pass
 if previous is not None:start=ref+previous
 def calc(x):
  if 'x' in cache and np.array_equal(x,cache['x']):return cache
  f=frame.copy();f[ids]=x;p,r=g.fk(f);g.set_pose(p,r);floors=g.floors()
  # Fixed XY and actual collider support height; orientation stays as close as
  # possible to the authored one. Floor clearance applies to upper/middle too.
  eq=np.r_[p[end,:2]-target_xy,floors[endgeom].min()-desired_bottom]
  cost=150*np.sum((p[upper+1]-knee_target)**2)+2*np.sum((r[bodies]-ref_rot[bodies])**2)+.03*np.sum((x-ref)**2)
  if previous is not None:cost+=5*np.sum((x-ref-previous)**2)
  cache.update(x=x.copy(),f=f,p=p,r=r,cost=cost,eq=eq,ineq=floors[geom]-C)
  return cache
 bounds=[(float(x-1.2),float(x+1.2)) for x in ref]
 # Hinge solutions must retain the original branch; no knee/elbow inversion.
 hinge=g.k.get_joint(upper+1);meta=next(x for x in g.meta['joints'] if x['body']==g.names[upper+1])
 bounds[3]=(min(meta['range_rad'][0],ref[3])-.001,max(meta['range_rad'][1],ref[3])+.001)
 result=minimize(lambda x:calc(x)['cost'],start,method='SLSQP',bounds=bounds,
  constraints=[dict(type='eq',fun=lambda x:calc(x)['eq']),dict(type='ineq',fun=lambda x:calc(x)['ineq'])],
  options=dict(maxiter=120,ftol=1e-10,eps=1e-6))
 # A floor fix must not introduce a new joint violation or deepen an existing
 # self-overlap. Preserve pre-existing user-authored overlap rather than using
 # it as permission for a wholesale sitting-pose replacement.
 candidates=[pair for pair in g.pairs if any(g.gb[z] in bodies for z in pair)
             and not (upper>=9 and any(g.gb[z]>=3 and g.gb[z] not in bodies for z in pair))]
 baseline=g.distances(original,candidates);g.distances(calc(result.x)['f'])
 near=[(pair,min(0.,d)-.0002) for pair,d in zip(candidates,baseline) if g.distance(*pair)<.03 or d<.03]
 lower=np.minimum(0,margins(g,original,bodies))-.00001
 def no_regression(x):
  c=calc(x);g.set_pose(c['p'],c['r'])
  return np.r_[margins(g,c['f'],bodies)-lower,[g.distance(*pair)-floor for pair,floor in near]]
 if no_regression(result.x).min()<-.00002:
  result=minimize(lambda x:calc(x)['cost'],result.x,method='SLSQP',bounds=bounds,
   constraints=[dict(type='eq',fun=lambda x:calc(x)['eq']),dict(type='ineq',fun=lambda x:calc(x)['ineq']),dict(type='ineq',fun=no_regression)],
   options=dict(maxiter=150,ftol=1e-9,eps=1e-6))
 relaxed=False
 if no_regression(result.x).min()<-.00005 or max(abs(calc(result.x)['eq']))>2e-5:
  # Thick colliders may make exact original XY incompatible with floor and
  # self-contact. Permit at most 2 cm, penalized strongly, rather than twisting
  # the limb through a joint limit or deepening an overlap.
  relaxed=True
  result=minimize(lambda x:calc(x)['cost']+10000*np.sum(calc(x)['eq'][:2]**2),result.x,method='SLSQP',bounds=bounds,
   constraints=[dict(type='eq',fun=lambda x:calc(x)['eq'][2:]),dict(type='ineq',fun=lambda x:np.r_[calc(x)['ineq'],.02**2-np.sum(calc(x)['eq'][:2]**2)]),dict(type='ineq',fun=no_regression)],
   options=dict(maxiter=200,ftol=1e-9,eps=1e-6))
 c=calc(result.x)
 eq_bad=abs(c['eq'][2])>2e-5 or (np.linalg.norm(c['eq'][:2])>.02001 if relaxed else max(abs(c['eq'][:2]))>2e-5)
 if eq_bad or min(c['ineq'])< -2e-5 or no_regression(result.x).min()<-.00005:
  np.savez(OUT/'failed-chain.npz',frame=frame,original=original,after=c['f'])
  raise RuntimeError(dict(body=g.names[upper],success=bool(result.success),message=result.message,eq=c['eq'].tolist(),floor=float(min(c['ineq'])),regression=float(no_regression(result.x).min()),regression_index=int(no_regression(result.x).argmin()),limits_count=len(lower),pairs=[(g.gs[a]['name'],g.gs[b]['name']) for (a,b),_ in near]))
 return c['f'],result.x-ref

def clean(name):
 g=Geometry();src=P/'motions'/f'{name}.pkl';m=pickle.loads(src.read_bytes());frames=m['frames'].astype(float)
 if name=='crawl':
  # Dense keys preserve the same duration and original trajectory while allowing
  # contact correction through the rapid hand/foot rotations between 30 Hz keys.
  frames=interpolate(g,frames,4);m=dict(m,fps=m['fps']*4)
 ps,rs,bs,root,targets=plan(g,name,frames);out=[];previous={};started=time.time()
 # Saved sitting is a single authored pose. Solve once, then repeat exactly.
 count=1 if np.max(abs(frames-frames[0]))<1e-10 else len(frames)
 for i in range(count):
  f=frames[i].copy();f[2]+=root[i]
  if name.startswith('crawl'):f=reachable_torso(g,f,frames[i],ps[i],rs[i],bs[i],targets,i)
  for upper in [9,12,3,6]:
   end=upper+2
   if end not in targets:continue
   knee=ps[i,upper+1].copy();knee[2]+=root[i]
   if name.startswith('crawl') and upper>=9:
    # Preserve raised knees during swing; place planted knees above their actual
    # thick capsule support instead of assuming the joint center is the surface.
    b=bs[i,np.isin(g.gb,[upper,upper+1])].min()
    knee[2]=ps[i,upper+1,2]+max(0,C-b)
   f,previous[upper]=chain(g,f,frames[i],upper,float(targets[end][i]),ps[i,end,:2],knee,rs[i],previous.get(upper))
  if name=='sitting':
   # Preserve each hand's user-authored attachment relative to its same shin.
   np_,nr=g.fk(f)
   for upper,shin in [(3,9),(6,13)]:
    hand=upper+2;anchor=rs[i,shin].T@(ps[i,hand]-ps[i,shin]);target=np_[shin]+nr[shin]@anchor
    g.set_pose(np_,nr);oldbottom=g.floors()[g.gb==hand].min();desired=oldbottom+target[2]-np_[hand,2]
    f,_=chain(g,f,frames[i],upper,float(desired),target[:2],ps[i,upper+1]+[0,0,root[i]],rs[i])
  out.append(f)
  if i%15==0:print(name,i,count,round(time.time()-started,1),flush=True)
 if count==1:out=out*len(frames)
 out=np.array(out)
 np.savez_compressed(OUT/(name+'-solved.npz'),frames=out,source_frames=frames)
 # Evaluate exact training quaternion interpolation at 32 subdivisions. A small
 # shared root clearance envelope removes between-keyframe sag without changing
 # limb pose. Reject large sag: that requires a better trajectory, not a lift.
 dense=interpolate(g,out,32);_,_,db=sample(g,dense);mins=db.min(1)
 extra=np.zeros(len(out))
 for i in range(len(out)-1):
  lift=max(0,.0005-float(mins[i*32:(i+1)*32+1].min()))
  extra[i:i+2]=np.maximum(extra[i:i+2],lift)
 if extra.max()>.006:raise RuntimeError((name,'interpolation sag >6mm',float(extra.max())))
 out[:,2]+=extra
 dense=interpolate(g,out,32);dp,dr,db=sample(g,dense)
 assert db.min()>-.00001,(name,db.min())
 assert np.array_equal(out[:,:2],frames[:,:2]);assert np.array_equal(out[:,3:6],frames[:,3:6]);assert np.array_equal(out[:,9:12],frames[:,9:12])
 if not name.startswith('crawl'):assert np.array_equal(out[:,6:9],frames[:,6:9])
 path=OUT/'candidates'/f'{name}.pkl';path.parent.mkdir(parents=True,exist_ok=True)
 path.write_bytes(pickle.dumps(dict(m,frames=out)))
 before=sample(g,frames)[2];ap,ar,ab=sample(g,out)
 perbody={n:dict(before_min_cm=float(before[:,g.gb==b].min()*100),after_min_cm=float(db[:,g.gb==b].min()*100),after_max_cm=float(db[:,g.gb==b].min(1).max()*100)) for b,n in enumerate(g.names)}
 report=dict(description=DESCRIPTIONS[name],source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),candidate_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
  frames=len(out),fps=m['fps'],dense_samples=len(dense),before_min_cm=float(before.min()*100),after_min_cm=float(db.min()*100),root_shift_cm=[float((out[:,2]-frames[:,2]).min()*100),float((out[:,2]-frames[:,2]).max()*100)],
  interpolation_lift_cm=float(extra.max()*100),max_body_displacement_cm=float(np.linalg.norm(ap-ps,axis=-1).max()*100),body_floor=perbody,
  before_geometry=g.audit(frames),after_geometry=g.audit(out),target_bottoms_cm={g.names[k]:(v*100).tolist() for k,v in targets.items()})
 (OUT/'candidates'/f'{name}.json').write_text(json.dumps(report,indent=2))
 print('DONE',name,'floor',report['after_min_cm'],'root',report['root_shift_cm'],'seconds',round(time.time()-started,1),flush=True)
 return report

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('names',nargs='*');a=parser.parse_args();OUT.mkdir(exist_ok=True)
 for name in a.names or NAMES:clean(name)
 reports={p.stem:json.loads(p.read_text()) for p in (OUT/'candidates').glob('*.json')}
 (OUT/'report.json').write_text(json.dumps(reports,indent=2))
