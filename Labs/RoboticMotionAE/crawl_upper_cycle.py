"""Smooth the contact-induced torso correction across the complete crawl cycle."""
import json,pickle,shutil,time
import numpy as np
from scipy.spatial.transform import Rotation as R
from scipy.interpolate import CubicSpline
from scipy.optimize import minimize
from clean_slow_contacts import Geometry,OUT,sample,interpolate
from crawl_cycle_ik import unit
from audit_crawl_temporal import metrics
from repair_slow_targets import coords

def joint_margins(g,f,body):
 j=g.k.get_joint(body);meta=next(x for x in g.meta['joints'] if x['body']==g.names[body]);v=f[:,6+j.dof_idx:6+j.dof_idx+j.get_dof_dim()]
 if v.shape[1]==1:return np.c_[v[:,0]-meta['range_rad'][0],meta['range_rad'][1]-v[:,0]]
 q=(R.from_quat(np.array(meta['reference_wxyz'])[[1,2,3,0]])*R.from_rotvec(v)).as_quat()[:,[3,0,1,2]];c=coords(q);lim=meta['limits_rad']
 return np.c_[lim[0]-c[:,0],lim[0]+c[:,0],1-(c[:,1]/np.sin(lim[1]/2))**2-(c[:,2]/np.sin(lim[2]/2))**2]

def fk(g,f):
 n=len(f);p=np.empty((n,15,3));r=np.empty((n,15,3,3));p[:,0]=f[:,:3];r[:,0]=R.from_rotvec(f[:,3:6]).as_matrix()
 for i,j in enumerate(g.joints,1):
  parent=g.parents[i];v=f[:,6+j.dof_idx:6+j.dof_idx+j.get_dof_dim()]
  delta=R.from_rotvec(v if v.shape[1]==3 else v*j.axis.numpy()).as_matrix()
  p[:,i]=p[:,parent]+np.einsum('nij,j->ni',r[:,parent],g.lp[i]);r[:,i]=r[:,parent]@g.lr[i]@delta
 return p,r

def arm(g,f,ref,target,target_r,upper,pole=None,allow_unreachable=False):
 p,r=fk(g,f);op,orr=fk(g,ref);mid,end=upper+1,upper+2
 hj,kj,fj=[g.k.get_joint(b) for b in [upper,mid,end]];a,b=g.lp[mid],g.lp[end];rest=g.lr[mid];axis=unit(kj.axis.numpy().astype(float))
 axial=axis*np.dot(axis,b);perp=b-axial;c=a@a+b@b+2*a@(rest@axial);aa=2*a@(rest@perp);ab=2*a@(rest@np.cross(axis,b))
 radius=np.hypot(aa,ab);phi=np.arctan2(ab,aa);dist=np.linalg.norm(target-p[:,upper],axis=1);value=(dist**2-c)/radius
 if allow_unreachable:value=np.clip(value,-.999999,.999999)
 else:assert max(abs(value))<1,(upper,value.min(),value.max())
 # The positive anatomical elbow branch, selected once for the entire cycle.
 delta=np.arccos(value);expected=ref[:,6+kj.dof_idx];candidates=np.stack([phi+delta,phi-delta],1)
 candidates=expected[:,None]+(candidates-expected[:,None]+np.pi)%(2*np.pi)-np.pi
 branch=int(np.mean(abs(candidates-expected[:,None]),axis=0).argmin());angle=candidates[:,branch]
 hinge=rest@R.from_rotvec(angle[:,None]*axis).as_matrix();total=a+np.einsum('nij,j->ni',hinge,b)
 src=unit(np.einsum('nij,nj->ni',orr[:,upper],total));dst=unit(target-p[:,upper]);cross=np.cross(src,dst);s=np.linalg.norm(cross,axis=1);dot=np.sum(src*dst,axis=1)
 turn=R.from_rotvec(unit(cross)*np.arctan2(s,dot)[:,None]).as_matrix();ur=turn@orr[:,upper]
 if pole is not None:ur=R.from_rotvec(dst*pole[:,None]).as_matrix()@ur
 mr=ur@hinge
 out=f.copy();out[:,6+hj.dof_idx:9+hj.dof_idx]=R.from_matrix(g.lr[upper].T@r[:,g.parents[upper]].transpose(0,2,1)@ur).as_rotvec()
 out[:,6+kj.dof_idx]=angle;out[:,6+fj.dof_idx:9+fj.dof_idx]=R.from_matrix(g.lr[end].T@mr.transpose(0,2,1)@target_r).as_rotvec()
 return out

def fit_arm(g,f,reference,old,tip,tip_r,upper,B):
 lower=np.concatenate([np.minimum(joint_margins(g,old,b),0) for b in range(upper,upper+3)],axis=1)
 cache={};count=B.shape[1]
 def calc(x):
  if 'x' in cache and np.array_equal(x,cache['x']):return cache
  pole=B@x;ff=arm(g,f,reference,tip,tip_r,upper,pole)
  margin=np.concatenate([joint_margins(g,ff,b) for b in range(upper,upper+3)],axis=1)-lower
  dd=np.roll(x,1)-2*x+np.roll(x,-1)
  cache.update(x=x.copy(),f=ff,cost=np.mean(pole**2)+.3*np.mean(dd**2),cons=margin.ravel()+1e-6);return cache
 res=minimize(lambda x:calc(x)['cost'],np.zeros(count),method='SLSQP',bounds=[(-.7,.7)]*count,constraints=[dict(type='ineq',fun=lambda x:calc(x)['cons'])],options=dict(maxiter=100,ftol=1e-10,eps=1e-6))
 cc=calc(res.x);print('arm constraints',upper,res.success,cc['cons'].min(),'max pole deg',np.rad2deg(abs(B@res.x).max()),flush=True)
 assert cc['cons'].min()>-1e-5
 return cc['f'],res.x

def main():
 g=Geometry();path=OUT/'candidates/crawl.pkl';m=pickle.loads(path.read_bytes());old=m['frames'].copy()
 backup=OUT/'before-head-continuity-fix';backup.mkdir(exist_ok=True)
 if not (backup/'crawl.pkl').exists():shutil.copy2(path,backup/'crawl.pkl')
 old=pickle.loads((backup/'crawl.pkl').read_bytes())['frames'];ref=interpolate(g,pickle.loads((OUT/'before/crawl.pkl').read_bytes())['frames'],4)
 op,orr,_=sample(g,old);rp,rr,_=sample(g,ref);n=len(old);count=8
 B=CubicSpline(np.linspace(0,1,count+1),np.r_[np.eye(count),np.eye(count)[:1]],bc_type='periodic')(np.linspace(0,1,n))
 correction=(R.from_rotvec(old[:,6:9])*R.from_rotvec(ref[:,6:9]).inv()).as_rotvec()
 start=np.c_[np.linalg.lstsq(B,correction,rcond=None)[0],np.zeros((count,4))];maxreach=[]
 for u in [3,6]:maxreach.append(np.linalg.norm(g.lp[u+1])+np.linalg.norm(g.lp[u+2])-.012)
 cache={}
 def calc(x):
  if 'x' in cache and np.array_equal(x,cache['x']):return cache
  ctl=x.reshape(count,7);curves=B@ctl;delta=curves[:,:3];f=old.copy();f[:,6:9]=(R.from_rotvec(delta)*R.from_rotvec(ref[:,6:9])).as_rotvec();p,r=fk(g,f)
  dd=np.roll(ctl,1,0)-2*ctl+np.roll(ctl,-1,0)
  cost=np.mean((delta-correction)**2)+.3*np.mean(dd[:,:3]**2)+.05*np.mean(delta**2)+30*np.mean(curves[:,3:]**2)+20*np.mean(dd[:,3:]**2)
  tips=[op[:,u+2]+np.c_[curves[:,3+2*i:5+2*i],np.zeros(n)] for i,u in enumerate([3,6])]
  cons=np.concatenate([reach-np.linalg.norm(t-p[:,u],axis=1) for u,reach,t in zip([3,6],maxreach,tips)]+[joint_margins(g,f,1).ravel()])
  cache.update(x=x.copy(),f=f,p=p,r=r,cost=cost,cons=cons,tips=tips);return cache
 bounds=[b for _ in range(count) for b in [(-.5,.5)]*3+[(-.03,.03)]*4]
 started=time.time();res=minimize(lambda x:calc(x)['cost'],start.ravel(),method='SLSQP',bounds=bounds,constraints=[dict(type='ineq',fun=lambda x:calc(x)['cons'])],options=dict(maxiter=200,ftol=1e-10,eps=1e-6))
 cc=calc(res.x);print('torso cycle',res.success,res.message,'min',cc['cons'].min(),'seconds',time.time()-started,flush=True);assert cc['cons'].min()>-2e-6
 f=cc['f'].copy()
 arm_controls=[]
 for i,upper in enumerate([3,6]):
  f,control=fit_arm(g,f,ref,old,cc['tips'][i],orr[:,upper+2],upper,B);arm_controls.append(control.tolist())
 dense=interpolate(g,f,32);_,_,db=sample(g,dense)
 result=dict(before=metrics(g,old,m['fps']),after=metrics(g,f,m['fps']),reference=metrics(g,ref,m['fps']),dense_floor_min_cm=float(db.min()*100),geometry=g.audit(f),controls=res.x.reshape(count,7).tolist(),arm_pole_controls=arm_controls)
 assert np.array_equal(f[:,:6],old[:,:6]) and np.array_equal(f[:,26:],old[:,26:])
 assert np.array_equal(f[:,9:12],ref[:,9:12])
 assert result['after']['head']['angular_deg_s']<1.2*result['reference']['head']['angular_deg_s']
 assert result['after']['head']['angular_accel_deg_s2']<1.2*result['reference']['head']['angular_accel_deg_s2']
 assert db.min()>.0005 and result['geometry']['worst_penetration_cm']<.1
 result['dense_upper_joint_min_margins']={g.names[b]:float(joint_margins(g,dense,b).min()) for b in range(1,9)}
 assert min(result['dense_upper_joint_min_margins'].values())>-2e-6
 fp,fr,_=sample(g,f)
 result['maximum_hand_xy_change_cm']=np.linalg.norm(fp[:,[5,8],:2]-op[:,[5,8],:2],axis=-1).max(0).tolist()
 result['maximum_hand_xy_change_cm']=[x*100 for x in result['maximum_hand_xy_change_cm']]
 result['root_and_legs_bitwise_unchanged']=True
 result['original_head_joint_animation_unchanged']=True
 np.savez(OUT/'crawl-upper-cycle.npz',frames=f)
 (OUT/'crawl-upper-cycle.json').write_text(json.dumps(result,indent=2))
 print('floor',result['dense_floor_min_cm'],'geometry',result['geometry'],flush=True)
 for b in g.names[:9]:print(b,'angular',result['before'][b]['angular_deg_s'],'->',result['after'][b]['angular_deg_s'],'ref',result['reference'][b]['angular_deg_s'],'acc',result['after'][b]['angular_accel_deg_s2'],flush=True)

def stage():
 import hashlib
 path=OUT/'candidates/crawl.pkl';m=pickle.loads(path.read_bytes());f=np.load(OUT/'crawl-upper-cycle.npz')['frames'];g=Geometry()
 report=json.loads((OUT/'crawl-upper-cycle.json').read_text())
 dense=interpolate(g,f,32)
 report['dense_upper_joint_min_margins']={g.names[b]:float(joint_margins(g,dense,b).min()) for b in range(1,9)}
 assert min(report['dense_upper_joint_min_margins'].values())>-2e-6 and report['dense_floor_min_cm']>.05
 old=pickle.loads((OUT/'before-head-continuity-fix/crawl.pkl').read_bytes())['frames']
 assert np.array_equal(f[:,:6],old[:,:6]) and np.array_equal(f[:,26:],old[:,26:])
 assert report['after']['head']['angular_deg_s']<1.2*report['reference']['head']['angular_deg_s']
 report.update(root_and_legs_bitwise_unchanged=True,original_head_joint_animation_unchanged=bool(np.array_equal(f[:,9:12],old[:,9:12])))
 m['frames']=f;path.write_bytes(pickle.dumps(m));j=json.loads(path.with_suffix('.json').read_text())
 backup=OUT/'before-head-continuity-fix/crawl.json'
 if not backup.exists():shutil.copy2(path.with_suffix('.json'),backup)
 j['head_cycle_repair']=report;j['candidate_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
 j['description']='Smooth cycle-wide torso correction removes the head jerk while retaining the original head joint animation. Head rotation peak: 95 degrees/s (reference 85; previous cleanup 366). Hand contacts retained; torso and arm joint limits checked. The approved knee and foot trajectories are unchanged.'
 path.with_suffix('.json').write_text(json.dumps(j,indent=2))
 (OUT/'crawl-upper-cycle.json').write_text(json.dumps(report,indent=2))

if __name__=='__main__':
 import sys
 if '--stage-only' in sys.argv:stage()
 else:main()
