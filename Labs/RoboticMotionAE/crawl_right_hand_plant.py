"""Anchor the right palm during stance, smooth its swing, preserve head/legs."""
from crawl_upper_cycle import *
import hashlib
from scipy.ndimage import gaussian_filter1d
from scipy.optimize import least_squares

def main():
 g=Geometry();path=OUT/'candidates/crawl.pkl';m=pickle.loads(path.read_bytes())
 backup=OUT/'before-right-hand-plant';backup.mkdir(exist_ok=True)
 if not (backup/'crawl.pkl').exists():
  shutil.copy2(path,backup/'crawl.pkl');shutil.copy2(path.with_suffix('.json'),backup/'crawl.json')
 old=pickle.loads((backup/'crawl.pkl').read_bytes())['frames'];ref=interpolate(g,pickle.loads((OUT/'before/crawl.pkl').read_bytes())['frames'],4)
 op,orr=fk(g,old);rp,rr=fk(g,ref);n=len(old);phase=np.linspace(0,54,n);stance=(phase<=12)|(phase>=36)
 gi=next(i for i,s in enumerate(g.gs) if s['name']=='hand_r_shape0')
 base=R.from_matrix(rr[stance,5]).mean().as_matrix();displacement=old[-1,:3]-old[0,:3];displacement[2]=0
 anchor=(op[:,5,:2]-np.where((phase>=36)[:,None],displacement[:2],0))[stance].mean(0);u=np.clip((phase-12)/24,0,1)
 swing=~stance;ease=u**3*(10-15*u+6*u*u);envelope=np.where(swing,np.sin(np.pi*u)**2,0)
 relative=gaussian_filter1d(R.from_matrix(rr[:,5]@base.T).as_rotvec(),9,axis=0,mode='wrap');count=12
 B=CubicSpline(np.linspace(0,1,count+1),np.r_[np.eye(count),np.eye(count)[:1]],bc_type='periodic')(np.linspace(0,1,n))
 # Use a separating plane for the palm versus the thigh through the swing.
 # Normal is fixed from the preceding solve; box support is recomputed per pose.
 probe=OUT/'right-hand-plant-probe.npz'
 seed=m['frames']
 sp,sr=fk(g,seed);ti=next(i for i,s in enumerate(g.gs) if s['name']=='thigh_r_shape0')
 tc=op[:,9]+np.einsum('nij,j->ni',orr[:,9],g.gp[ti]);tr=orr[:,9]@g.gr[ti];axis=tr[:,:,2];half=g.gs[ti]['size'][1]
 hc=sp[:,5]+np.einsum('nij,j->ni',sr[:,5],g.gp[gi])
 near=tc+axis*np.clip(np.sum((hc-tc)*axis,axis=1),-half,half)[:,None];normal=unit(hc-near)
 capsule_support=g.gs[ti]['size'][0]+half*abs(np.sum(axis*normal,axis=1))
 seed_hr=sr[:,5]@g.gr[gi]
 seed_gap=np.sum((hc-tc)*normal,axis=1)-capsule_support-np.sum(np.abs(np.einsum('nji,nj->ni',seed_hr,normal))*g.gs[gi]['size'],axis=1)
 collision_ids=np.flatnonzero(seed_gap<.025)
 print('collision keys',len(collision_ids),flush=True)
 cache={};it=0
 def calc(x):
  if 'x' in cache and np.array_equal(x,cache['x']):return cache
  rot=R.from_rotvec(x[2:5]+envelope[:,None]*x[19:22]).as_matrix()@R.from_rotvec(relative*envelope[:,None]*.3).as_matrix()@base
  tip=np.zeros((n,3));tip[:,:2]=anchor+x[:2]
  tip[:,:2]+=ease[:,None]*displacement[:2]
  tip[:,1]+=envelope*x[17]
  gr=rot@g.gr[gi];tip[:,2]=.0015+np.abs(gr[:,2])@g.gs[gi]['size']-np.einsum('nij,j->ni',rot,g.gp[gi])[:,2]+envelope*x[18]
  f=arm(g,old,ref,tip,rot,3,B@x[5:17],allow_unreachable=True)
  cons=[np.linalg.norm(g.lp[4])+np.linalg.norm(g.lp[5])-.002-np.linalg.norm(tip-op[:,3],axis=1)]
  cons += [joint_margins(g,f,b).ravel()+1e-6 for b in [3,4,5]]
  cons.append(gr[stance,2,1]-np.cos(np.deg2rad(35)))
  hc=tip+np.einsum('nij,j->ni',rot,g.gp[gi])
  box_support=np.sum(np.abs(np.einsum('nji,nj->ni',gr,normal))*g.gs[gi]['size'],axis=1)
  cons.append((np.sum((hc-tc)*normal,axis=1)-capsule_support-box_support-.002)[collision_ids])
  dd=np.roll(x[5:17],1)-2*x[5:17]+np.roll(x[5:17],-1)
  cost=100*np.mean(x[:2]**2)+np.mean(x[2:5]**2)+.03*np.mean(x[5:17]**2)+2*x[17]**2+20*(x[18]-.13)**2+.05*np.mean(x[19:22]**2)+.2*np.mean(dd**2)
  cache.update(x=x.copy(),f=f,cons=np.concatenate(cons),cost=cost,tip=tip,rot=rot);return cache
 def progress(x):
  nonlocal it
  it+=1
  if it%10==0:print(it,calc(x)['cons'].min(),calc(x)['cons'].argmin(),flush=True)
 probe=OUT/'right-hand-plant-probe.npz';start=np.load(probe)['parameters'] if probe.exists() else np.zeros(5+count)
 if len(start)==17:start=np.r_[start,.08]
 start=np.zeros(22);start[:2]=[-.0136423943,-.0127078872];start[2:5]=[.2,-.1,0];start[17]=.002;start[18]=.18;start[19:22]=[-.5,.6,.08]
 bounds=[(-.15,.15)]*2+[(-.6,.6)]*3+[(-3.,3.)]*count+[(0,.2),(.08,.32)]+[(-1.5,1.5)]*3
 if '--stage-probe' in __import__('sys').argv:
  from types import SimpleNamespace
  res=SimpleNamespace(x=np.load(probe)['parameters'],success=True,message='Stage previously solved parameters; revalidate all constraints')
 else:
  feasible=least_squares(lambda x:np.r_[np.minimum(calc(x)['cons'],0),.001*(x-start)],start,bounds=np.array(bounds).T,max_nfev=160,ftol=1e-8,xtol=1e-8,gtol=1e-8)
  print('feasibility',calc(feasible.x)['cons'].min(),flush=True)
  res=minimize(lambda x:calc(x)['cost'],feasible.x,method='SLSQP',bounds=bounds,constraints=[dict(type='ineq',fun=lambda x:calc(x)['cons'])],callback=progress,options=dict(maxiter=160,ftol=1e-9,eps=1e-6))
 c=calc(res.x);print(res.success,res.message,c['cons'].min(),flush=True);np.savez(OUT/'right-hand-plant-probe.npz',frames=c['f'],parameters=res.x)
 assert c['cons'].min()>-2e-6
 f=c['f'];dense=interpolate(g,f,16);p,r=fk(g,dense);_,_,bottom=sample(g,dense);times=np.linspace(0,54,len(dense));mask=(times<=12)|(times>=36)
 planted=p[:,5].copy();planted[times>=36]-=displacement
 report=dict(stance_translation_range_cm=(np.ptp(planted[mask],axis=0)*100).tolist(),stance_rotation_error_deg=float(np.rad2deg(R.from_matrix(r[mask,5]@r[mask,5][0].T).magnitude()).max()),floor_min_cm=float(bottom.min()*100),geometry=g.audit(interpolate(g,f,4)),joint_margins={g.names[b]:float(joint_margins(g,dense,b).min()) for b in [3,4,5]},before=metrics(g,old,m['fps']),after=metrics(g,f,m['fps']),anchor_offset_cm=(res.x[:2]*100).tolist())
 (OUT/'right-hand-plant.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ['before','after']},indent=2),flush=True)
 assert bottom.min()>.0005 and report['geometry']['worst_penetration_cm']<.1
 assert min(report['joint_margins'].values())>-2e-5
 assert max(report['stance_translation_range_cm'])<.05 and report['stance_rotation_error_deg']<.05
 reference_metrics=metrics(g,ref,m['fps']);report['reference']=reference_metrics
 assert report['after']['right_hand']['angular_deg_s']<.6*reference_metrics['right_hand']['angular_deg_s']
 assert report['after']['right_hand']['angular_accel_deg_s2']<10000
 j=g.k.get_joint(3);end=6+g.k.get_joint(6).dof_idx;assert np.array_equal(f[:,:6+j.dof_idx],old[:,:6+j.dof_idx]) and np.array_equal(f[:,end:],old[:,end:])
 report['palm_tilt_limit_deg']=35;report['stance_source_frames']=[[0,12],[36,54]];report['swing_lift_cm']=float(res.x[18]*100)
 (OUT/'right-hand-plant.json').write_text(json.dumps(report,indent=2))
 m['frames']=f;path.write_bytes(pickle.dumps(m));meta=json.loads(path.with_suffix('.json').read_text());meta['right_hand_plant']=report;meta['candidate_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();meta['description']='Both palms hold their floor positions during stance. Pink hand sliding corrected, with a smooth thigh-clearing swing. Head-height and leg corrections retained. Preview only; live training unchanged.';path.with_suffix('.json').write_text(json.dumps(meta,indent=2))

if __name__=='__main__':main()

