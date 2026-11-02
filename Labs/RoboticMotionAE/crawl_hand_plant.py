"""Anchor the left palm during stance, smooth its swing, preserve head/legs."""
from crawl_upper_cycle import *
import hashlib
from scipy.ndimage import gaussian_filter1d

def main():
 g=Geometry();path=OUT/'candidates/crawl.pkl';m=pickle.loads(path.read_bytes())
 backup=OUT/'before-left-hand-plant';backup.mkdir(exist_ok=True)
 if not (backup/'crawl.pkl').exists():
  shutil.copy2(path,backup/'crawl.pkl');shutil.copy2(path.with_suffix('.json'),backup/'crawl.json')
 old=pickle.loads((backup/'crawl.pkl').read_bytes())['frames'];ref=interpolate(g,pickle.loads((OUT/'before/crawl.pkl').read_bytes())['frames'],4)
 op,orr=fk(g,old);rp,rr=fk(g,ref);n=len(old);phase=np.linspace(0,54,n);stance=(phase>=11)&(phase<=43)
 gi=next(i for i,s in enumerate(g.gs) if s['name']=='hand_l_shape0')
 base=R.from_matrix(rr[stance,8]).mean().as_matrix();displacement=old[-1,:3]-old[0,:3];displacement[2]=0
 anchor=op[stance,8,:2].mean(0);u=np.where(phase<11,(phase+11)/22,(phase-43)/22);u=np.clip(u,0,1)
 swing=~stance;ease=u**3*(10-15*u+6*u*u);envelope=np.where(swing,np.sin(np.pi*u)**2,0)
 relative=gaussian_filter1d(R.from_matrix(rr[:,8]@base.T).as_rotvec(),9,axis=0,mode='wrap');count=12
 B=CubicSpline(np.linspace(0,1,count+1),np.r_[np.eye(count),np.eye(count)[:1]],bc_type='periodic')(np.linspace(0,1,n))
 cache={};it=0
 def calc(x):
  if 'x' in cache and np.array_equal(x,cache['x']):return cache
  rot=R.from_rotvec(x[2:5]).as_matrix()@R.from_rotvec(relative*envelope[:,None]).as_matrix()@base
  tip=np.zeros((n,3));tip[:,:2]=anchor+x[:2]
  tip[:,:2]+=np.where((phase<11)[:,None],(ease-1)[:,None]*displacement[:2],np.where((phase>43)[:,None],ease[:,None]*displacement[:2],0))
  gr=rot@g.gr[gi];tip[:,2]=.0015+np.abs(gr[:,2])@g.gs[gi]['size']-np.einsum('nij,j->ni',rot,g.gp[gi])[:,2]+envelope*.13
  f=arm(g,old,ref,tip,rot,6,B@x[5:],allow_unreachable=True)
  cons=[np.linalg.norm(g.lp[7])+np.linalg.norm(g.lp[8])-.002-np.linalg.norm(tip-op[:,6],axis=1)]
  cons += [joint_margins(g,f,b).ravel()+1e-6 for b in [6,7,8]]
  dd=np.roll(x[5:],1)-2*x[5:]+np.roll(x[5:],-1)
  cost=100*np.mean(x[:2]**2)+np.mean(x[2:5]**2)+.03*np.mean(x[5:]**2)+.2*np.mean(dd**2)
  cache.update(x=x.copy(),f=f,cons=np.concatenate(cons),cost=cost,tip=tip,rot=rot);return cache
 def progress(x):
  nonlocal it
  it+=1
  if it%10==0:print(it,calc(x)['cons'].min(),flush=True)
 probe=OUT/'left-hand-plant-probe.npz';start=np.load(probe)['parameters'] if probe.exists() else np.zeros(5+count)
 res=minimize(lambda x:calc(x)['cost'],start,method='SLSQP',bounds=[(-.15,.15)]*2+[(-.6,.6)]*3+[(-1.5,1.5)]*count,constraints=[dict(type='ineq',fun=lambda x:calc(x)['cons'])],callback=progress,options=dict(maxiter=160,ftol=1e-9,eps=1e-6))
 c=calc(res.x);print(res.success,res.message,c['cons'].min(),flush=True);np.savez(OUT/'left-hand-plant-probe.npz',frames=c['f'],parameters=res.x)
 assert c['cons'].min()>-2e-6
 f=c['f'];dense=interpolate(g,f,16);p,r=fk(g,dense);_,_,bottom=sample(g,dense);times=np.linspace(0,54,len(dense));mask=(times>=11)&(times<=43)
 report=dict(stance_translation_range_cm=(np.ptp(p[mask,8],axis=0)*100).tolist(),stance_rotation_error_deg=float(np.rad2deg(R.from_matrix(r[mask,8]@r[mask,8][0].T).magnitude()).max()),floor_min_cm=float(bottom.min()*100),geometry=g.audit(interpolate(g,f,4)),joint_margins={g.names[b]:float(joint_margins(g,dense,b).min()) for b in [6,7,8]},before=metrics(g,old,m['fps']),after=metrics(g,f,m['fps']),anchor_offset_cm=(res.x[:2]*100).tolist())
 (OUT/'left-hand-plant.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ['before','after']},indent=2),flush=True)
 assert bottom.min()>.0005 and report['geometry']['worst_penetration_cm']<.1
 assert min(report['joint_margins'].values())>-2e-5
 assert max(report['stance_translation_range_cm'])<.05 and report['stance_rotation_error_deg']<.05
 assert report['after']['left_hand']['angular_deg_s']<500
 assert report['after']['left_hand']['angular_accel_deg_s2']<10000
 j=g.k.get_joint(6);assert np.array_equal(f[:,:6+j.dof_idx],old[:,:6+j.dof_idx]) and np.array_equal(f[:,26:],old[:,26:])
 m['frames']=f;path.write_bytes(pickle.dumps(m));meta=json.loads(path.with_suffix('.json').read_text());meta['left_hand_plant']=report;meta['candidate_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();meta['description']='Left hand holds a fixed world pose through stance, with smooth swing and touchdown. Head-height correction and legs retained. Preview only; live training unchanged.';path.with_suffix('.json').write_text(json.dumps(meta,indent=2))

if __name__=='__main__':main()

