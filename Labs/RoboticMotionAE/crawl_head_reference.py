"""Preserve reference head orientation with a constant torso correction."""
from crawl_upper_cycle import *
import hashlib

def main():
 g=Geometry();path=OUT/'candidates/crawl.pkl';m=pickle.loads(path.read_bytes())
 backup=OUT/'before-head-reference-fix';backup.mkdir(exist_ok=True)
 if not (backup/'crawl.pkl').exists():
  shutil.copy2(path,backup/'crawl.pkl');shutil.copy2(path.with_suffix('.json'),backup/'crawl.json')
 old=pickle.loads((backup/'crawl.pkl').read_bytes())['frames'];ref=interpolate(g,pickle.loads((OUT/'before/crawl.pkl').read_bytes())['frames'],4)
 op,orr=fk(g,old);rp,rr=fk(g,ref);n=len(old);count=8
 B=CubicSpline(np.linspace(0,1,count+1),np.r_[np.eye(count),np.eye(count)[:1]],bc_type='periodic')(np.linspace(0,1,n))
 cache={}
 def calc(x):
  if 'x' in cache and np.array_equal(x,cache['x']):return cache
  f=old.copy();tr=R.from_rotvec(x[:3]).as_matrix()@rr[:,1]
  f[:,6:9]=R.from_matrix(g.lr[1].T@orr[:,0].transpose(0,2,1)@tr).as_rotvec()
  f[:,9:12]=R.from_matrix(g.lr[2].T@tr.transpose(0,2,1)@rr[:,2]).as_rotvec()
  p,r=fk(g,f);controls=x[3:].reshape(count,4);curves=B@controls
  tips=[op[:,u+2]+np.c_[curves[:,2*i:2*i+2],np.zeros(n)] for i,u in enumerate([3,6])]
  cons=[np.linalg.norm(g.lp[u+1])+np.linalg.norm(g.lp[u+2])-.002-np.linalg.norm(t-p[:,u],axis=1) for u,t in zip([3,6],tips)]
  cons += [joint_margins(g,f,b).ravel() for b in [1,2]]
  head_delta=(p[:,2]-p[:,0])-(rp[:,2]-rp[:,0]);head_variation=head_delta-head_delta.mean(0)
  dd=np.roll(controls,1,0)-2*controls+np.roll(controls,-1,0)
  cost=2*np.mean(x[:3]**2)+30*np.mean(curves**2)+20*np.mean(dd**2)+100*np.mean(head_variation**2)
  cache.update(x=x.copy(),f=f,tips=tips,cost=cost,cons=np.concatenate(cons));return cache
 start=np.r_[R.from_matrix(orr[:,1]@rr[:,1].transpose(0,2,1)).mean().as_rotvec(),np.zeros(count*4)]
 res=minimize(lambda x:calc(x)['cost'],start,method='SLSQP',bounds=[(-.5,.5)]*3+[(-.07,.07)]*(count*4),constraints=[dict(type='ineq',fun=lambda x:calc(x)['cons'])],options=dict(maxiter=200,ftol=1e-10,eps=1e-6))
 c=calc(res.x);print('constant torso',res.success,c['cons'].min(),res.message,flush=True);assert c['cons'].min()>-2e-6
 f=c['f']
 for i,u in enumerate([3,6]):f,_=fit_arm(g,f,ref,old,c['tips'][i],orr[:,u+2],u,B)
 dense=interpolate(g,f,32);_,_,bottom=sample(g,dense);p,r=fk(g,f)
 error=np.rad2deg(R.from_matrix(r[:,2]@rr[:,2].transpose(0,2,1)).magnitude())
 report=dict(head_orientation_error_max_deg=float(error.max()),before_head_orientation_error_max_deg=float(np.rad2deg(R.from_matrix(orr[:,2]@rr[:,2].transpose(0,2,1)).magnitude()).max()),head_relative_root_range_cm={k:(np.ptp(pp[:,2]-pp[:,0],axis=0)*100).tolist() for k,pp in [('reference',rp),('before',op),('after',p)]},constant_torso_world_correction_deg=np.rad2deg(res.x[:3]).tolist(),floor_min_cm=float(bottom.min()*100),geometry=g.audit(f),before=metrics(g,old,m['fps']),after=metrics(g,f,m['fps']),reference=metrics(g,ref,m['fps']),upper_joint_margins={g.names[b]:float(joint_margins(g,dense,b).min()) for b in range(1,9)})
 assert error.max()<1e-8 and bottom.min()>.0005
 assert min(report['upper_joint_margins'].values())>-2e-6
 assert report['geometry']['worst_penetration_cm']<.1
 assert np.array_equal(f[:,:6],old[:,:6]) and np.array_equal(f[:,26:],old[:,26:])
 np.savez(OUT/'crawl-head-reference.npz',frames=f)
 (OUT/'crawl-head-reference.json').write_text(json.dumps(report,indent=2))
 print(json.dumps({k:v for k,v in report.items() if k not in ['before','after','reference']},indent=2),flush=True)

if __name__=='__main__':main()

