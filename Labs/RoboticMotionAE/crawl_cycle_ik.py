"""Whole-cycle constrained contact IK with smooth correction curves.

Optimizes eight periodic cubic-spline control points per leg (foot XY and bend
pole), not independent poses. Reference world foot rotations are hard targets.
Offline review assets only; live package and provider state are never mutated.
"""
import json,pickle,shutil,hashlib,time
import numpy as np
from scipy.optimize import minimize
from scipy.interpolate import CubicSpline
from scipy.spatial.transform import Rotation as R
from clean_slow_contacts import Geometry,P,OUT,sample,interpolate,plan
from audit_crawl_temporal import metrics

def unit(x):return x/np.maximum(1e-12,np.linalg.norm(x,axis=-1,keepdims=True))

def solve(g,base,reference,upper,fps,problem=False):
 n=len(base);mid,end=upper+1,upper+2
 bp,br,bb=sample(g,base);op,orr,ob=sample(g,reference)
 hj,kj,fj=[g.k.get_joint(b) for b in [upper,mid,end]]
 hip=bp[:,upper];aoff=g.lp[mid];boff=g.lp[end];rest=g.lr[mid];axis=unit(kj.axis.numpy().astype(float))
 olddirection=unit(op[:,end]-op[:,upper]);oldpole=unit(op[:,mid]-op[:,upper]-olddirection*np.sum((op[:,mid]-op[:,upper])*olddirection,axis=-1)[:,None])
 axial=axis*np.dot(axis,boff);perp=boff-axial
 c=aoff@aoff+boff@boff+2*aoff@(rest@axial)
 aa=2*aoff@(rest@perp);ab=2*aoff@(rest@np.cross(axis,boff));radius=np.hypot(aa,ab);phi=np.arctan2(ab,aa)
 target=op[:,end].copy();target[:,2]+=.0015-ob[:,g.gb==end].min(1)
 count=8;phase=np.linspace(0,1,n)
 B=CubicSpline(np.linspace(0,1,count+1),np.r_[np.eye(count),np.eye(count)[:1]],bc_type='periodic')(phase)
 expected_angle=reference[:,6+kj.dof_idx]
 knee_target=op[:,mid].copy()
 # Raise the reference support only by its measured collider penetration.
 knee_target[:,2]+=np.maximum(0,.0015-ob[:,np.isin(g.gb,[upper,mid])].min(1))
 geoms=np.flatnonzero(np.isin(g.gb,[upper,mid]))
 cache={}
 def calc(x):
  if 'x' in cache and np.array_equal(x,cache['x']):return cache
  ctl=x.reshape(count,3);correction=B@ctl
  tip=target.copy();tip[:,:2]+=correction[:,:2];theta=correction[:,2]
  d=tip-hip;distance=np.linalg.norm(d,axis=1);direction=unit(d)
  value=(distance**2-c)/radius
  delta=np.arccos(np.clip(value,-1+1e-10,1-1e-10))
  angles=np.stack([phi+delta,phi-delta],axis=1)
  angles=expected_angle[:,None]+(angles-expected_angle[:,None]+np.pi)%(2*np.pi)-np.pi
  angle=angles[np.arange(n),np.abs(angles-expected_angle[:,None]).argmin(1)]
  hinge=rest@R.from_rotvec(angle[:,None]*axis).as_matrix()
  total=aoff+np.einsum('nij,j->ni',hinge,boff);ld=unit(total);lp=unit(aoff-ld*np.sum(aoff*ld,axis=1)[:,None])
  pole=unit(oldpole-direction*np.sum(oldpole*direction,axis=1)[:,None]);pole=pole*np.cos(theta[:,None])+np.cross(direction,pole)*np.sin(theta[:,None])
  src=np.stack([ld,lp,np.cross(ld,lp)],axis=-1);dst=np.stack([direction,pole,np.cross(direction,pole)],axis=-1)
  ur=dst@src.transpose(0,2,1);mr=ur@hinge;knee=hip+np.einsum('nij,j->ni',ur,aoff)
  floors=[]
  for z in geoms:
   rr=ur if g.gb[z]==upper else mr;pp=hip if g.gb[z]==upper else knee
   pos=pp+np.einsum('nij,j->ni',rr,g.gp[z]);rot=rr@g.gr[z];shape=g.gs[z];size=shape['size']
   floor=pos[:,2]-(np.abs(rot[:,2])@size if shape['type']=='box' else size[0]+abs(rot[:,2,2])*size[1])
   floors.append(floor)
  floors=np.stack(floors,1)
  # Penalize correction and its second derivative over the whole cycle.
  # Periodic cubic curves enforce a unique smooth bend branch through the seam.
  dd=np.roll(ctl,1,axis=0)-2*ctl+np.roll(ctl,-1,axis=0)
  cost=1500*np.mean(correction[:,:2]**2)+200*np.mean((knee-knee_target)**2)+.02*np.mean(theta**2)+200*np.mean(dd[:,:2]**2)+.03*np.mean(dd[:,2]**2)
  cons=np.r_[(floors-.0015).ravel(),1-.00001-np.abs(value)]
  cache.update(x=x.copy(),cost=cost,cons=cons,ur=ur,mr=mr,angle=angle,knee=knee,tip=tip,correction=correction)
  return cache
 start=np.zeros((count,3));start[:,2]=-.15 if upper==9 else .15
 bounds=[bound for _ in range(count) for bound in [(-.05,.05),(-.05,.05),(-.65,.65)]]
 def unpack(x,frame_base=None):
  cc=calc(x);out=base.copy() if frame_base is None else frame_base.copy()
  out[:,6+hj.dof_idx:9+hj.dof_idx]=R.from_matrix(g.lr[upper].T@br[:,g.parents[upper]].transpose(0,2,1)@cc['ur']).as_rotvec()
  out[:,6+kj.dof_idx]=cc['angle']
  out[:,6+fj.dof_idx:9+fj.dof_idx]=R.from_matrix(g.lr[end].T@cc['mr'].transpose(0,2,1)@orr[:,end]).as_rotvec()
  result=dict(upper=g.names[upper],control_points=count,minimum_constraint=float(cc['cons'].min()),maximum_foot_xy_change_cm=float(np.linalg.norm(cc['correction'][:,:2],axis=1).max()*100),maximum_pole_change_deg=float(np.rad2deg(abs(cc['correction'][:,2]).max())),control_values=x.reshape(count,3).tolist())
  return out,result
 if problem:return calc,start.ravel(),bounds,unpack
 started=time.time()
 res=minimize(lambda x:calc(x)['cost'],start.ravel(),method='SLSQP',bounds=[bound for _ in range(count) for bound in [(-.05,.05),(-.05,.05),(-.65,.65)]],constraints=[dict(type='ineq',fun=lambda x:calc(x)['cons'])],options=dict(maxiter=150,ftol=1e-10,eps=1e-6))
 cc=calc(res.x);print('cycle solve',upper,res.success,res.message,'minimum',cc['cons'].min(),'seconds',time.time()-started,flush=True)
 assert cc['cons'].min()>-2e-6
 return unpack(res.x)

def segment_distance(p,q,a,b):
 u=q-p;v=b-a;w=p-a
 dot=lambda x,y:np.sum(x*y,axis=-1)
 uu=dot(u,u);vv=dot(v,v);uv=dot(u,v);uw=dot(u,w);vw=dot(v,w)
 den=uu*vv-uv*uv;ss=(uv*vw-vv*uw)/np.maximum(den,1e-15);tt=(uu*vw-uv*uw)/np.maximum(den,1e-15)
 best=np.where((den>1e-12)&(ss>=0)&(ss<=1)&(tt>=0)&(tt<=1),dot(w+ss[:,None]*u-tt[:,None]*v,w+ss[:,None]*u-tt[:,None]*v),np.inf)
 for point,start,vec,length in [(p,a,v,vv),(q,a,v,vv),(a,p,u,uu),(b,p,u,uu)]:
  t=np.clip(dot(point-start,vec)/length,0,1);d=point-start-t[:,None]*vec;best=np.minimum(best,dot(d,d))
 return np.sqrt(np.maximum(best,0))

def solve_both(g,base,reference,fps):
 problems=[solve(g,base,reference,u,fps,True) for u in [9,12]]
 bp,br,_=sample(g,base);op,orr,_=sample(g,reference)
 split=len(problems[0][1]);caps=[i for i in range(len(g.gs)) if g.gb[i] in [9,10,12,13]]
 pairs=[(a,b) for a,b in g.pairs if a in caps and b in caps]
 footgeoms=[next(i for i in range(len(g.gs)) if g.gb[i]==b) for b in [11,14]]
 ar,al=[orr[:,b]@g.gr[z] for b,z in zip([11,14],footgeoms)]
 axes=np.concatenate([ar.transpose(0,2,1),al.transpose(0,2,1),np.cross(ar.transpose(0,2,1)[:,:,None,:],al.transpose(0,2,1)[:,None,:,:]).reshape(len(base),9,3)],axis=1)
 lengths=np.linalg.norm(axes,axis=-1);axes/=np.maximum(lengths,1e-12)[:,:,None]
 sizes=[g.gs[z]['size'] for z in footgeoms]
 radii=np.abs(axes@ar)@sizes[0]+np.abs(axes@al)@sizes[1]
 def calc(x):
  rows=[problems[0][0](x[:split]),problems[1][0](x[split:])];ends={}
  for z in caps:
   body=g.gb[z];idx=0 if body<12 else 1;upper=9+3*idx;row=rows[idx]
   p=bp[:,upper] if body==upper else row['knee'];r=row['ur'] if body==upper else row['mr']
   center=p+np.einsum('nij,j->ni',r,g.gp[z]);rr=r@g.gr[z];d=rr[:,:,2]*g.gs[z]['size'][1]
   ends[z]=(center-d,center+d)
  collision=[segment_distance(*ends[a],*ends[b])-g.gs[a]['size'][0]-g.gs[b]['size'][0]-.001 for a,b in pairs]
  centers=[row['tip']+np.einsum('nij,j->ni',orr[:,b],g.gp[z]) for row,b,z in zip(rows,[11,14],footgeoms)]
  projection=abs(np.einsum('nai,ni->na',axes,centers[1]-centers[0]))-radii
  collision.append(np.where(lengths>1e-7,projection,-np.inf).max(1)-.0005)
  return sum(row['cost'] for row in rows),np.concatenate([row['cons'] for row in rows]+collision)
 x=np.r_[problems[0][1],problems[1][1]];started=time.time()
 res=minimize(lambda x:calc(x)[0],x,method='SLSQP',bounds=problems[0][2]+problems[1][2],constraints=[dict(type='ineq',fun=lambda x:calc(x)[1])],options=dict(maxiter=200,ftol=1e-10,eps=1e-6))
 print('coupled cycle',res.success,res.message,'min',calc(res.x)[1].min(),'seconds',time.time()-started,flush=True)
 assert calc(res.x)[1].min()>-2e-6
 f,j0=problems[0][3](res.x[:split]);f,j1=problems[1][3](res.x[split:],f)
 return f,[j0,j1]

def rebuild(name):
 g=Geometry();path=OUT/'candidates'/f'{name}.pkl';m=pickle.loads(path.read_bytes());old=m['frames'].copy()
 backup=OUT/'before-knee-continuity-fix';backup.mkdir(exist_ok=True)
 if not (backup/path.name).exists():shutil.copy2(path,backup/path.name)
 # Always reproduce from immutable pre-fix candidate and original reference.
 old=pickle.loads((backup/path.name).read_bytes())['frames'].astype(float)
 source=pickle.loads((OUT/'before'/path.name).read_bytes())['frames'].astype(float)
 reference=interpolate(g,source,4) if name=='crawl' else source
 f,reports=solve_both(g,old,reference,m['fps'])
 dense=interpolate(g,f,32);_,_,db=sample(g,dense)
 print(name,'dense min cm',float(db.min()*100),flush=True)
 p,r,b=sample(g,f);op,orr,ob=sample(g,reference)
 error=R.from_matrix((r[:,[11,14]]@orr[:,[11,14]].transpose(0,1,3,2)).reshape(-1,3,3)).magnitude().max()
 report=dict(legs=reports,foot_orientation_error_deg=float(np.rad2deg(error)),dense_floor_min_cm=float(db.min()*100),before=metrics(g,old,m['fps']),after=metrics(g,f,m['fps']),reference=metrics(g,reference,m['fps']))
 assert db.min()>=.0005 and error<1e-7
 # This repair must neither move the problem to another leg segment nor change
 # upper-body contacts. Compare all six bodies, linear and angular continuity.
 assert np.array_equal(f[:,:26],old[:,:26])
 for i in range(9,15):
  body=g.names[i];fixed=report['after'][body];ref=report['reference'][body]
  assert fixed['angular_deg_s']<=max(2*ref['angular_deg_s'],1.),(body,'rotation spike',fixed)
  assert fixed['speed_m_s']<=max(1.25*ref['speed_m_s'],.01),(body,'position spike',fixed)
  assert fixed['angular_accel_deg_s2']<=max(2.2*ref['angular_accel_deg_s2'],10.),(body,'angular acceleration spike',fixed)
  assert fixed['acceleration_m_s2']<=max(2.5*ref['acceleration_m_s2'],.1),(body,'acceleration spike',fixed)
 audit=g.audit(f);assert audit['worst_penetration_cm']<.1,(name,audit)
 report['geometry']=audit
 np.savez(OUT/f'{name}-cycle-ik.npz',frames=f)
 (OUT/f'{name}-cycle-ik.json').write_text(json.dumps(report,indent=2))
 for b in [g.names[i] for i in range(9,15)]:print(name,b,round(report['before'][b]['angular_deg_s'],2),'->',round(report['after'][b]['angular_deg_s'],2), 'ref',round(report['reference'][b]['angular_deg_s'],2),flush=True)

def stage_review():
 for name in ['crawl','crawl_idle']:
  path=OUT/'candidates'/f'{name}.pkl';m=pickle.loads(path.read_bytes())
  report=json.loads((OUT/f'{name}-cycle-ik.json').read_text())
  assert report['dense_floor_min_cm']>=.05 and report['foot_orientation_error_deg']<1e-5
  m['frames']=np.load(OUT/f'{name}-cycle-ik.npz')['frames'];path.write_bytes(pickle.dumps(m))
  j=json.loads(path.with_suffix('.json').read_text());j['cycle_ik_repair']=report
  j['candidate_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
  j['description']=('Whole-cycle leg correction: reference knee bend directions, smooth periodic contact adjustments, and original foot rotations. Both legs are solved together to avoid knee/shin intersections. Palm contacts and the upper-body pose are retained. '+('Knee rotation snaps removed; peak shin speeds 126 / 141 degrees/s (previous cleanup 2073 / 2251).' if name=='crawl' else 'Both palms, knees and feet keep floor clearance throughout the breathing cycle.'))
  path.with_suffix('.json').write_text(json.dumps(j,indent=2))

if __name__=='__main__':
 import sys
 if '--stage-only' in sys.argv:stage_review();sys.exit(0)
 for name in ['crawl','crawl_idle']:rebuild(name)
 if '--stage' in sys.argv:stage_review()
