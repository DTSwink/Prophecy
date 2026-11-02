"""Small coupled-leg correction after independent contact IK; offline only."""
import json,pickle,sys,time,hashlib
import numpy as np
from scipy.optimize import minimize
from clean_slow_contacts import Geometry,OUT,P,NAMES,sample,interpolate,margins

def polish(name):
 g=Geometry();path=OUT/'candidates'/f'{name}.pkl';m=pickle.loads(path.read_bytes());frames=m['frames'];original=pickle.loads((P/'motions'/path.name).read_bytes())['frames'].astype(float)
 if len(original)!=len(frames):original=interpolate(g,original,round((len(frames)-1)/(len(original)-1)))
 ids=np.arange(6+g.k.get_joint(9).dof_idx,40);leggeom=np.flatnonzero(g.gb>=9)
 pairs=[pair for pair in g.pairs if any(g.gb[z]>=9 for z in pair)]
 out=[];count=0;starttime=time.time();maxxy=0.
 for tick,(f,orig) in enumerate(zip(frames,original)):
  lower=np.minimum(0,g.distances(orig,pairs))-.0003
  ds=g.distances(f,pairs)
  if np.min(ds-lower)>=-.00001:out.append(f);continue
  count+=1;refp,refr=g.fk(f);g.set_pose(refp,refr);floors=g.floors();footheight=[floors[g.gb==b].min() for b in [11,14]]
  limitlower=np.minimum(0,margins(g,orig,range(9,15)))-.00002
  active=[k for k in range(len(pairs)) if ds[k]<.05 or lower[k]<-.001];cache={}
  def calc(x):
   if 'x' in cache and np.array_equal(x,cache['x']):return cache
   ff=f.copy();ff[ids]=x;p,r=g.fk(ff);g.set_pose(p,r);b=g.floors()
   eq=np.array([b[g.gb==body].min()-height for body,height in zip([11,14],footheight)])
   cost=500*np.sum((p[9:]-refp[9:])**2)+5*np.sum((r[9:]-refr[9:])**2)+np.sum((x-f[ids])**2)
   collision=np.array([g.distance(*pairs[k])-lower[k] for k in active])
   xy=p[[11,14],:2]-refp[[11,14],:2]
   cons=np.r_[b[leggeom]-.0005,collision,margins(g,ff,range(9,15))-limitlower,.04**2-(xy**2).sum(1)]
   cache.update(x=x.copy(),f=ff,cost=cost,eq=eq,ineq=cons,p=p);return cache
  result=minimize(lambda x:calc(x)['cost'],f[ids],method='SLSQP',bounds=[(x-.3,x+.3) for x in f[ids]],
   constraints=[dict(type='eq',fun=lambda x:calc(x)['eq']),dict(type='ineq',fun=lambda x:calc(x)['ineq'])],
   options=dict(maxiter=100,ftol=1e-9,eps=1e-6))
  c=calc(result.x)
  if abs(c['eq']).max()>2e-5 or c['ineq'].min()<-.00005:raise RuntimeError((name,tick,result.message,float(c['ineq'].min()),c['eq'].tolist()))
  out.append(c['f']);maxxy=max(maxxy,float(np.linalg.norm(c['p'][[11,14],:2]-refp[[11,14],:2],axis=1).max()))
  if count%15==0:print(name,'polished',count,'frame',tick,'s',round(time.time()-starttime,1),flush=True)
 out=np.array(out);dense=interpolate(g,out,32);_,_,db=sample(g,dense);extra=np.zeros(len(out))
 for i in range(len(out)-1):extra[i:i+2]=np.maximum(extra[i:i+2],max(0,.0005-db[i*32:(i+1)*32+1].min()))
 if extra.max()>.006:raise RuntimeError((name,'large interpolation sag',extra.max()))
 out[:,2]+=extra;dense=interpolate(g,out,32);_,_,db=sample(g,dense)
 assert db.min()>=-1e-5
 path.write_bytes(pickle.dumps(dict(m,frames=out)));reportpath=path.with_suffix('.json');j=json.loads(reportpath.read_text())
 j.update(candidate_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),after_min_cm=float(db.min()*100),after_geometry=g.audit(out),
  coupled_leg_polish=dict(frames=count,max_extra_foot_xy_cm=maxxy*100,max_extra_root_cm=float(extra.max()*100),seconds=time.time()-starttime))
 for body,n in enumerate(g.names):j['body_floor'][n].update(after_min_cm=float(db[:,g.gb==body].min()*100),after_max_cm=float(db[:,g.gb==body].min(1).max()*100))
 reportpath.write_text(json.dumps(j,indent=2));print('POLISHED',name,count,'xycm',maxxy*100,flush=True)

if __name__=='__main__':
 for name in sys.argv[1:] or NAMES:polish(name)
