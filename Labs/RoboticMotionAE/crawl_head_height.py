"""Coupled torso/arm cycle solve with reference head height and orientation."""
from crawl_upper_cycle import *
import hashlib

def main():
 g=Geometry();path=OUT/'candidates/crawl.pkl';m=pickle.loads(path.read_bytes())
 backup=OUT/'before-head-height-fix';backup.mkdir(exist_ok=True)
 if not (backup/'crawl.pkl').exists():
  shutil.copy2(path,backup/'crawl.pkl');shutil.copy2(path.with_suffix('.json'),backup/'crawl.json')
 old=pickle.loads((backup/'crawl.pkl').read_bytes())['frames'];ref=interpolate(g,pickle.loads((OUT/'before/crawl.pkl').read_bytes())['frames'],4)
 op,orr=fk(g,old);rp,rr=fk(g,ref);n=len(old);count=8
 B=CubicSpline(np.linspace(0,1,count+1),np.r_[np.eye(count),np.eye(count)[:1]],bc_type='periodic')(np.linspace(0,1,n))
 delta=(R.from_rotvec(old[:,6:9])*R.from_rotvec(ref[:,6:9]).inv()).as_rotvec()
 initial=np.zeros((count,9));initial[:,:3]=np.linalg.lstsq(B,delta,rcond=None)[0]
 # IK poles relative to reference, already validated in the previous torso solve.
 prior=json.loads((OUT/'crawl-upper-cycle.json').read_text())
 initial[:,7:]=np.array(prior['arm_pole_controls']).T
 probe=OUT/'crawl-head-height-probe.npz'
 collision=None
 if probe.exists():
  saved=np.load(probe);initial=saved['controls'].reshape(count,9)
  pp,pr=fk(g,saved['frames']);hi=next(i for i,s in enumerate(g.gs) if s['name']=='hand_r_shape0');ti=next(i for i,s in enumerate(g.gs) if s['name']=='thigh_r_shape0')
  hc=pp[:,5]+np.einsum('nij,j->ni',pr[:,5],g.gp[hi]);tc=pp[:,9]+np.einsum('nij,j->ni',pr[:,9],g.gp[ti]);hr=pr[:,5]@g.gr[hi];tr=pr[:,9]@g.gr[ti];axis=tr[:,:,2];half=g.gs[ti]['size'][1]
  near=tc+axis*np.clip(np.sum((hc-tc)*axis,axis=1),-half,half)[:,None];normal=unit(hc-near)
  extent=g.gs[ti]['size'][0]+half*abs(np.sum(axis*normal,axis=1))+np.sum(np.abs(np.einsum('nji,nj->ni',hr,normal))*g.gs[hi]['size'],axis=1)
  gap=np.sum((hc-tc)*normal,axis=1)-extent;ids=np.flatnonzero(gap<.015)
  collision=(hi,tc,normal,extent,ids)
 cache={};calls=0
 def calc(x):
  if 'x' in cache and np.array_equal(x,cache['x']):return cache
  ctl=x.reshape(count,9);curves=B@ctl;f=old.copy()
  f[:,6:9]=(R.from_rotvec(curves[:,:3])*R.from_rotvec(ref[:,6:9])).as_rotvec()
  p,r=fk(g,f);f[:,9:12]=R.from_matrix(g.lr[2].T@r[:,1].transpose(0,2,1)@rr[:,2]).as_rotvec()
  tips=[op[:,u+2]+np.c_[curves[:,3+i*2:5+i*2],np.zeros(n)] for i,u in enumerate([3,6])]
  cons=[np.linalg.norm(g.lp[u+1])+np.linalg.norm(g.lp[u+2])-.002-np.linalg.norm(t-p[:,u],axis=1) for u,t in zip([3,6],tips)]
  height=p[:,2,2]-rp[:,2,2]
  cons += [height+.001,.015-height]
  for i,u in enumerate([3,6]):f=arm(g,f,ref,tips[i],orr[:,u+2],u,curves[:,7+i],allow_unreachable=True)
  cons += [joint_margins(g,f,b).ravel()+1e-6 for b in range(1,9)]
  if collision is not None:
   hi,tc,normal,extent,ids=collision
   hc=tips[0]+np.einsum('nij,j->ni',orr[:,5],g.gp[hi])
   cons.append((np.sum((hc-tc)*normal,axis=1)-extent-.001)[ids])
  dd=np.roll(ctl,1,0)-2*ctl+np.roll(ctl,-1,0)
  pos=(p[:,2]-p[:,0])-(rp[:,2]-rp[:,0])
  cost=np.mean((curves[:,:3]-delta)**2)+100*np.mean(pos**2)+20*np.mean(curves[:,3:7]**2)+.02*np.mean(curves[:,7:]**2)+.4*np.mean(dd[:,:3]**2)+20*np.mean(dd[:,3:7]**2)+.1*np.mean(dd[:,7:]**2)
  cache.update(x=x.copy(),f=f,cost=cost,cons=np.concatenate(cons));return cache
 def progress(x):
  nonlocal calls
  calls+=1
  if calls%10==0:print('iteration',calls,'margin',calc(x)['cons'].min(),'index',calc(x)['cons'].argmin(),flush=True)
 res=minimize(lambda x:calc(x)['cost'],initial.ravel(),method='SLSQP',bounds=[b for _ in range(count) for b in [(-.6,.6)]*3+[(-.12,.12)]*4+[(-1.2,1.2)]*2],constraints=[dict(type='ineq',fun=lambda x:calc(x)['cons'])],callback=progress,options=dict(maxiter=180,ftol=1e-9,eps=1e-6))
 c=calc(res.x);print(res.success,res.message,c['cons'].min(),flush=True)
 np.savez(OUT/'crawl-head-height-probe.npz',frames=c['f'],controls=res.x)
 assert c['cons'].min()>-2e-6
 f=c['f'];dense=interpolate(g,f,32);rd=interpolate(g,ref,32);p,r=fk(g,dense);rp,rr=fk(g,rd);_,_,bottom=sample(g,dense)
 report=dict(head_height_error_cm=[float((p[:,2,2]-rp[:,2,2]).min()*100),float((p[:,2,2]-rp[:,2,2]).max()*100)],head_rotation_error_deg=float(np.rad2deg(R.from_matrix(r[:,2]@rr[:,2].transpose(0,2,1)).magnitude()).max()),floor_min_cm=float(bottom.min()*100),geometry=g.audit(f),joint_margins={g.names[b]:float(joint_margins(g,dense,b).min()) for b in range(1,9)},before=metrics(g,old,m['fps']),after=metrics(g,f,m['fps']),reference=metrics(g,ref,m['fps']))
 (OUT/'crawl-head-height.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ['before','after','reference']},indent=2),flush=True)
 assert bottom.min()>.0005 and report['geometry']['worst_penetration_cm']<.1
 assert min(report['joint_margins'].values())>-2e-4 and report['head_height_error_cm'][0]>-.12
 assert np.array_equal(f[:,:6],old[:,:6]) and np.array_equal(f[:,26:],old[:,26:])
 m['frames']=f;path.write_bytes(pickle.dumps(m));j=json.loads(path.with_suffix('.json').read_text())
 j['head_height_repair']=report;j['candidate_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();j['description']='Reference head height and orientation preserved throughout the cycle. Torso and arm IK solved together; palm heights and corrected legs retained. Preview only; live training unchanged.'
 path.with_suffix('.json').write_text(json.dumps(j,indent=2))

if __name__=='__main__':main()


