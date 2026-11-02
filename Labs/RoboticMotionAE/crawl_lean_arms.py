"""Coupled pelvis lean, exact leg compensation, planted palms and smooth bent arms."""
from crawl_upper_cycle import *
from scipy.optimize import least_squares
from scipy.ndimage import gaussian_filter1d
import hashlib

def main():
 g=Geometry();path=OUT/'candidates/crawl.pkl';m=pickle.loads(path.read_bytes());backup=OUT/'before-pelvis-arm-repair';backup.mkdir(exist_ok=True)
 if not (backup/'crawl.pkl').exists():
  shutil.copy2(path,backup/'crawl.pkl');shutil.copy2(path.with_suffix('.json'),backup/'crawl.json')
 old=pickle.loads((backup/'crawl.pkl').read_bytes())['frames'];ref=interpolate(g,pickle.loads((OUT/'before/crawl.pkl').read_bytes())['frames'],4)
 op,orr=fk(g,old);rp,rr=fk(g,ref);n=len(old);phase=np.linspace(0,54,n);dt=1/m['fps'];count=8
 # The reference guides the elbow plane, with a smooth cyclic guide rather than framewise twists.
 guide=ref.copy()
 for sl in [slice(3,6)]+[slice(6+j.dof_idx,9+j.dof_idx) for j in g.joints if j.get_dof_dim()==3]:
  rot=R.from_rotvec(ref[:,sl]).as_matrix();mean=R.from_matrix(rot).mean().as_matrix();v=R.from_matrix(rot@mean.T).as_rotvec();smooth=gaussian_filter1d(v[:-1],5,axis=0,mode='wrap');guide[:,sl]=R.from_matrix(R.from_rotvec(np.r_[smooth,smooth[:1]]).as_matrix()@mean).as_rotvec()
 B=CubicSpline(np.linspace(0,1,count+1),np.r_[np.eye(count),np.eye(count)[:1]],bc_type='periodic')(np.linspace(0,1,n))
 axis=unit(g.lp[9]-g.lp[12]);pivot=(g.lp[9]+g.lp[12])/2;displacement=old[-1,:3]-old[0,:3];displacement[2]=0
 hands=[]
 for upper,lo,hi in [(3,12,36),(6,43,65)]:
  end=upper+2;gi=next(i for i,s in enumerate(g.gs) if s['body']==g.names[end]);unwrapped=np.where(phase<lo,phase+54,phase) if hi>54 else phase
  u=np.clip((unwrapped-lo)/(hi-lo),0,1);swing=(unwrapped>lo)&(unwrapped<hi);envelope=np.where(swing,np.sin(np.pi*u)**2,0);ease=u**3*(10-15*u+6*u*u)
  stance=~swing;cycle_shift=np.where((phase<lo)[:,None],-displacement[:2],0) if hi>54 else np.zeros((n,2))
  offset=ease[:,None]*displacement[:2]+cycle_shift
  anchor=(op[:,end,:2]-offset)[stance].mean(0)
  geom=R.from_matrix(rr[stance,end]@g.gr[gi]).mean().as_matrix();long=geom[:,0].copy();long[2]=0;long=unit(long);normal=np.array([0.,0.,np.sign(geom[2,1])]);side=np.cross(long,normal)
  flat=np.stack([long,normal,side],axis=1)@g.gr[gi].T
  hands.append(dict(upper=upper,end=end,gi=gi,stance=stance,envelope=envelope,offset=offset,anchor=anchor,flat=flat))
 lower_thigh={b:np.minimum(joint_margins(g,old,b),0) for b in [9,12]}
 cache={};calls=0
 def calc(x):
  if 'x' in cache and np.array_equal(x,cache['x']):return cache
  f=old.copy();root=orr[:,0]@R.from_rotvec(axis*x[0]).as_matrix();f[:,3:6]=R.from_matrix(root).as_rotvec();f[:,:3]=old[:,:3]+np.einsum('nij,j->ni',orr[:,0]-root,pivot)
  for b in [9,12]:
   j=g.k.get_joint(b);f[:,6+j.dof_idx:9+j.dof_idx]=R.from_matrix(g.lr[b].T@root.transpose(0,2,1)@orr[:,b]).as_rotvec()
  f[:,6:9]=R.from_matrix(g.lr[1].T@R.from_rotvec(axis*x[-1]).as_matrix()@g.lr[1]@R.from_rotvec(old[:,6:9]).as_matrix()).as_rotvec()
  p,r=fk(g,f);f[:,9:12]=R.from_matrix(g.lr[2].T@r[:,1].transpose(0,2,1)@rr[:,2]).as_rotvec()
  cons=[];cost=.3*(x[0]-.15)**2+.5*x[-1]**2;targets=[]
  for i,h in enumerate(hands):
   a=1+i*(9+count);v=x[a:a+9+count];rot=R.from_rotvec(h['envelope'][:,None]*v[4+count:7+count]).as_matrix()@R.from_rotvec([v[7+count],v[8+count],v[2]]).as_matrix()@h['flat'];gr=rot@g.gr[h['gi']]
   tip=np.zeros((n,3));tip[:,:2]=h['anchor']+v[:2]+h['offset'];tip[:,2]=.0015+np.sqrt(gr[:,2]**2+.01**2)@g.gs[h['gi']]['size']-np.einsum('nij,j->ni',rot,g.gp[h['gi']])[:,2]+h['envelope']*v[3]
   targets.append(tip);cons.append(np.linalg.norm(g.lp[h['upper']+1])+np.linalg.norm(g.lp[h['end']])-.02-np.linalg.norm(tip-p[:,h['upper']],axis=1))
   f=arm(g,f,guide,tip,rot,h['upper'],B@v[4:4+count],allow_unreachable=True)
   dd=np.roll(v[4:4+count],1)-2*v[4:4+count]+np.roll(v[4:4+count],-1)
   cost+=30*np.mean(v[:2]**2)+.1*v[2]**2+3*(v[3]-.12)**2+.01*np.mean(v[4:4+count]**2)+.1*np.mean(dd**2)+.1*np.mean(v[4+count:7+count]**2)+.5*np.mean(v[7+count:9+count]**2)
  p,r=fk(g,f)
  for b in range(1,9):cons.append(joint_margins(g,f,b).ravel()+1e-6)
  for b in [9,12]:cons.append((joint_margins(g,f,b)-lower_thigh[b]).ravel()+1e-6)
  for b in [4,7]:
   acceleration=np.diff(p[:,b],n=2,axis=0)/dt**2;cost+=.0004*np.mean(acceleration**2)
   j=g.k.get_joint(b);acc=np.diff(f[:,6+j.dof_idx],n=2)/dt**2;cost+=.00002*np.mean(acc**2)
  # Exact support functions for all compound colliders, vectorized.
  floors=[]
  for gi,s in enumerate(g.gs):
   b=g.gb[gi];gr=r[:,b]@g.gr[gi];gp=p[:,b]+np.einsum('nij,j->ni',r[:,b],g.gp[gi]);extent=np.abs(gr[:,2])@s['size'] if s['type']=='box' else s['size'][0]+abs(gr[:,2,2])*s['size'][1]
   floors.append(gp[:,2]-extent)
  cons.append(np.array(floors).ravel()-.0005)
  cache.update(x=x.copy(),f=f,cost=cost,cons=np.concatenate(cons),p=p,r=r);return cache
 start=np.zeros(2+2*(9+count));start[0]=.2;start[-1]=.08
 bounds=[(0,.5)]
 for i in range(2):start[1+i*(9+count)+3]=.12;bounds += [(-.18,.18)]*2+[(-.5,.5),(.05,.24)]+[(-3.,3.)]*count+[(-.7,.7)]*3+[(-.2,.2)]*2
 bounds += [(0,.15)]
 probe=OUT/'pelvis-arms-probe.npz'
 if '--warm' in __import__('sys').argv and probe.exists():
  previous=np.load(probe)['parameters']
  if len(previous)==len(start):start=previous
  else:
   start[0]=previous[0];old_stride=(len(previous)-2)//2 if len(previous)%2==0 else (len(previous)-1)//2
   for i in range(2):start[1+i*17:1+i*17+old_stride]=previous[1+i*old_stride:1+(i+1)*old_stride]
   start[-1]=previous[-1] if len(previous)%2==0 else .08
 def progress(x):
  nonlocal calls
  calls+=1
  if calls%10==0:print(calls,'margin',calc(x)['cons'].min(),'at',calc(x)['cons'].argmin(),'cost',calc(x)['cost'],'lean',np.rad2deg(x[0]),flush=True)
 feasible=least_squares(lambda x:np.r_[np.minimum(calc(x)['cons'],0),.0003*(x-start)],start,bounds=np.array(bounds).T,max_nfev=120)
 print('feasible',calc(feasible.x)['cons'].min(),flush=True)
 res=minimize(lambda x:calc(x)['cost'],feasible.x,method='SLSQP',bounds=bounds,constraints=[dict(type='ineq',fun=lambda x:calc(x)['cons'])],callback=progress,options=dict(maxiter=180,ftol=1e-8,eps=1e-6))
 c=calc(res.x);np.savez(probe,frames=c['f'],parameters=res.x);print(res.success,res.message,'margin',c['cons'].min(),flush=True)
 assert c['cons'].min()>-2e-6
 f=c['f'];dense=interpolate(g,f,16);p,r,bottom=sample(g,dense);po,ro=fk(g,interpolate(g,old,16));report=dict(torso_extra_lean_deg=float(np.rad2deg(res.x[-1])),lean_deg=float(np.rad2deg(res.x[0])),before=metrics(g,old,m['fps']),after=metrics(g,f,m['fps']),reference=metrics(g,ref,m['fps']),geometry=g.audit(interpolate(g,f,4)),floor_min_cm=float(bottom.min()*100),leg_origin_error_cm=float(np.linalg.norm(p[:,9:]-po[:,9:],axis=-1).max()*100),leg_rotation_error_deg=float(np.rad2deg(R.from_matrix((r[:,9:]@ro[:,9:].transpose(0,1,3,2)).reshape(-1,3,3)).magnitude()).max()),joint_margins={g.names[b]:float(joint_margins(g,dense,b).min()) for b in range(1,15)})
 phase_dense=np.linspace(0,54,len(dense));quality={}
 for upper in [3,6]:
  end=upper+2;stance=((phase_dense<=12)|(phase_dense>=36)) if upper==3 else ((phase_dense>=11)&(phase_dense<=43));pp=p[:,end].copy()
  if upper==3:pp[phase_dense>=36]-=displacement
  bend=np.rad2deg(np.arccos(np.clip(np.sum(unit(p[:,upper+1]-p[:,upper])*unit(p[:,end]-p[:,upper+1]),axis=1),-1,1)))
  gi=next(i for i,shape in enumerate(g.gs) if shape['body']==g.names[end]);gr=r[:,end]@g.gr[gi]
  quality[g.names[end]]=dict(stance_position_range_mm=(np.ptp(pp[stance],axis=0)*1000).tolist(),minimum_elbow_bend_deg=float(bend.min()),maximum_palm_tilt_deg=float(np.rad2deg(np.arccos(np.clip(abs(gr[stance,2,1]),0,1))).max()))
 report['contact_quality']=quality
 assert max(max(q['stance_position_range_mm']) for q in quality.values())<.1
 assert min(q['minimum_elbow_bend_deg'] for q in quality.values())>25
 for b in [4,7]:assert report['after'][g.names[b]]['acceleration_m_s2']<.5*report['before'][g.names[b]]['acceleration_m_s2']
 (OUT/'pelvis-arms.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ['before','after','reference']},indent=2),flush=True)
 assert bottom.min()>.0004 and report['geometry']['arm_leg_worst_penetration_cm']<.1
 assert report['leg_origin_error_cm']<.1 and report['leg_rotation_error_deg']<.1
 assert min(report['joint_margins'][g.names[b]] for b in range(1,9))>-2e-5
 m['frames']=f;path.write_bytes(pickle.dumps(m));meta=json.loads(path.with_suffix('.json').read_text());meta.update(pelvis_arms=report,candidate_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),description='Forward pelvis lean with compensated thighs, unchanged leg paths, flatter planted palms and bent, smoother arms. Preview only; training unchanged.');path.with_suffix('.json').write_text(json.dumps(meta,indent=2))
if __name__=='__main__':main()

