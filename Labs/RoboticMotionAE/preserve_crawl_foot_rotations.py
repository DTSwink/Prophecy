"""Offline crawl contact IK with authored world foot rotations as hard targets."""
import json,pickle,hashlib,shutil,time
import numpy as np
from scipy.optimize import minimize
from scipy.spatial.transform import Rotation as R
from clean_slow_contacts import Geometry,OUT,P,sample,interpolate,solve_leg

def repair(name):
 g=Geometry();path=OUT/'candidates'/f'{name}.pkl';m=pickle.loads(path.read_bytes());before=m['frames'].copy()
 backup=OUT/'before-foot-rotation-fix';backup.mkdir(exist_ok=True)
 if not (backup/path.name).exists():shutil.copy2(path,backup/path.name)
 original=pickle.loads((P/'motions'/path.name).read_bytes())['frames'].astype(float)
 if len(original)!=len(before):original=interpolate(g,original,round((len(before)-1)/(len(original)-1)))
 op,orr,ob=sample(g,original);out=[];started=time.time()
 for tick,f in enumerate(before):
  f=f.copy()
  for upper in [9,12]:
   mid,end=upper+1,upper+2;hj,kj,fj=[g.k.get_joint(b) for b in [upper,mid,end]]
   ids=np.r_[np.arange(6+hj.dof_idx,9+hj.dof_idx),6+kj.dof_idx];fs=slice(6+fj.dof_idx,9+fj.dof_idx)
   p0,r0=g.fk(f);g.set_pose(p0,r0);height=max(.0015,float(g.floors()[g.gb==end].min()))
   desired=orr[tick,end];tmp=r0.copy();tmp[end]=desired;g.set_pose(p0,tmp)
   target=p0[end].copy();target[2]+=height-g.floors()[g.gb==end].min();start=f[ids].copy()
   try:
    ur,angle,mr,kp=solve_leg(p0[upper],p0[mid],p0[end],target,g.lp[mid],g.lp[end],g.lr[mid],kj.axis.numpy(),start[3])
    start[:3]=R.from_matrix(g.lr[upper].T@r0[g.parents[upper]].T@ur).as_rotvec();start[3]=angle
   except ValueError:pass
   cache={}
   def calc(x):
    if 'x' in cache and np.array_equal(x,cache['x']):return cache
    ff=f.copy();ff[ids]=x;p,r=g.fk(ff)
    ff[fs]=R.from_matrix(g.lr[end].T@r[mid].T@desired).as_rotvec();p,r=g.fk(ff);g.set_pose(p,r);b=g.floors()
    cost=400*np.sum((p[mid]-p0[mid])**2)+3000*np.sum((p[end,:2]-target[:2])**2)+.1*np.sum((r[upper]-r0[upper])**2)
    cache.update(x=x.copy(),f=ff,cost=cost,eq=b[g.gb==end].min()-height,ineq=b[np.isin(g.gb,[upper,mid]) ]-.001,p=p)
    return cache
   c=calc(start)
   if abs(c['eq'])>2e-5 or c['ineq'].min() < -2e-5:
    res=minimize(lambda x:calc(x)['cost'],start,method='SLSQP',constraints=[dict(type='eq',fun=lambda x:calc(x)['eq']),dict(type='ineq',fun=lambda x:calc(x)['ineq'])],options=dict(maxiter=50,ftol=1e-8,eps=1e-5))
    c=calc(res.x)
   assert abs(c['eq'])<2e-5 and c['ineq'].min()>-2e-5,(name,tick,upper,c['eq'],c['ineq'])
   f=c['f']
  out.append(f)
  if tick%40==0:print(name,tick,len(before),round(time.time()-started,1),flush=True)
 out=np.array(out);dense=interpolate(g,out,32);_,_,b=sample(g,dense);extra=np.zeros(len(out))
 for i in range(len(out)-1):extra[i:i+2]=np.maximum(extra[i:i+2],max(0,.0005-b[i*32:(i+1)*32+1].min()))
 assert extra.max()<.003,(name,extra.max())
 out[:,2]+=extra;p,r,b=sample(g,out)
 error=R.from_matrix((r[:,[11,14]]@orr[:,[11,14]].transpose(0,1,3,2)).reshape(-1,3,3)).magnitude()
 assert error.max()<1e-6
 def speeds(frames):
  _,rr,_=sample(g,frames);return (R.from_matrix((rr[1:,[11,14]]@rr[:-1,[11,14]].transpose(0,1,3,2)).reshape(-1,3,3)).magnitude().reshape(-1,2)*180/np.pi*m['fps']).max(0).tolist()
 report=dict(world_foot_rotation_error_degrees=float(error.max()*180/np.pi),previous_peak_deg_s=speeds(before),fixed_peak_deg_s=speeds(out),reference_peak_deg_s=speeds(original),root_extra_cm=float(extra.max()*100))
 path.write_bytes(pickle.dumps(dict(m,frames=out)));j=json.loads(path.with_suffix('.json').read_text());j.update(candidate_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),foot_rotation_repair=report);j['description']+=' Foot orientations now follow the original animation exactly; floor clearance is solved through leg placement.';path.with_suffix('.json').write_text(json.dumps(j,indent=2));print(report,flush=True)

if __name__=='__main__':
 for name in ['crawl','crawl_idle']:repair(name)
