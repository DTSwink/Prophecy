"""Offline constrained recovery cleanup. Original motions/PHAT remain untouched."""
import sys,json,pickle,hashlib,time
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R,Slerp
from scipy.optimize import minimize
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'Labs/MimicKitUEFN'),str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit')]
from fit_motion_limits import MJCFCharModel,sampled_coordinates,violation,coords
import torch
torch.set_num_threads(1)
ASSET=ROOT/'Saved/MimicKitEquipment/package/assets/uefn'
OUT=ROOT/'Saved/MimicKitEquipment/recovery-cleaned-preview';OUT.mkdir(exist_ok=True)
meta=json.loads((ASSET/'limits.json').read_text());model=MJCFCharModel('cpu');model.load(str(ASSET/'humanoid_uefn.xml'))
names=model.get_body_names();parents=np.asarray(model._parent_indices);lp=model._local_translation.numpy().astype(float);lr=R.from_quat(model._local_rotation.numpy()).as_matrix()
entries=[];bounds=[];ball_starts=[]
for i,name in enumerate(names[1:],1):
 j=next(x for x in meta['joints'] if x['body']==name);k=model.get_joint(i);start=len(bounds)
 if j['kind']=='ball':
  lim=np.array(j['limits_rad']);scale=np.sin(lim[1:]/2)*.998
  bounds.extend([(-lim[0]+.001,lim[0]-.001),(-1,1),(-1,1)]);ball_starts.append(start)
 else:
  scale=None;bounds.append((j['range_rad'][0]+.001,j['range_rad'][1]-.001))
 entries.append(dict(i=i,j=j,start=start,dof=k.dof_idx,scale=scale,ref=R.from_quat(np.array(j['reference_wxyz'])[[1,2,3,0]]).inv(),axis=k.axis.numpy() if j['kind']!='ball' else None))
bounds.append((0,.20));bounds=np.array(bounds)
shapes=[]
for g in meta['geometry']:
 i=names.index(g['body']);f=meta['body_frames'][g['body']];rest=R.from_quat(f['quaternion'])
 shapes.append((i,rest.inv().apply(np.array(g['position'])-f['position']),(rest.inv()*R.from_quat(g['quaternion'])).as_matrix(),g['type'],np.array(g['size'])))
gid=np.array([s[0] for s in shapes]);gp=np.array([s[1] for s in shapes]);gr=np.array([s[2] for s in shapes])
hands=[names.index(n+'_hand') for n in ('right','left')];feet=[names.index(n+'_foot') for n in ('right','left')];effectors=hands+feet

def encode(frame):
 x=np.zeros(35)
 for e in entries:
  a=e['start'];d=e['dof'];j=e['j']
  if j['kind']=='ball':
   full=e['ref'].inv()*R.from_rotvec(frame[6+d:9+d]);v=coords(full.as_quat()[[3,0,1,2]])
   x[a]=np.clip(v[0],*bounds[a]);x[a+1:a+3]=v[1:]/e['scale'];x[a+1:a+3]/=max(1,np.linalg.norm(x[a+1:a+3]))
  else:x[a]=np.clip(frame[6+d],*bounds[a])
 return x

def decode(x,frame):
 local=np.empty((14,3,3));dof=np.zeros(34)
 for e in entries:
  a=e['start'];d=e['dof'];i=e['i']
  if e['j']['kind']=='ball':
   t=x[a];y,z=x[a+1:a+3]*e['scale'];w=np.sqrt(max(1e-12,1-y*y-z*z));c=np.cos(t/2);s=np.sin(t/2)
   rot=e['ref']*R.from_quat([w*s,y*c+z*s,z*c-y*s,w*c]);dof[d:d+3]=rot.as_rotvec()
  else:rot=R.from_rotvec(e['axis']*x[a]);dof[d]=x[a]
  local[i-1]=lr[i]@rot.as_matrix()
 p=np.zeros((15,3));rot=np.zeros((15,3,3));p[0]=frame[:3];p[0,2]+=x[-1];rot[0]=R.from_rotvec(frame[3:6]).as_matrix()
 for i in range(1,15):
  p[i]=p[parents[i]]+rot[parents[i]]@lp[i];rot[i]=rot[parents[i]]@local[i-1]
 return p,rot,dof

def heights(p,r):
 centres=p[gid]+np.einsum('nij,nj->ni',r[gid],gp);rot=r[gid]@gr;extent=[]
 for k,(_,_,_,kind,size) in enumerate(shapes):
  extent.append(np.abs(rot[k,2])@size if kind=='box' else size[0]+size[1]*abs(rot[k,2,2]) if kind=='capsule' else size[0])
 return centres[:,2]-extent

def clean(frames,clearances=None,only=None):
 result=[];stats=[];previous_offset=None
 for f,frame in enumerate(frames):
  if only is not None and f not in only:
   result.append(frame);stats.append(dict(frame=f,unchanged=True));previous_offset=None;continue
  x0=encode(frame);p0,r0,_=decode(x0,frame);h0=heights(p0,r0)
  floor=np.full(len(shapes),.002) if clearances is None else clearances[f]
  # Root height only clears the pelvis's own collider. Hands/feet are solved by IK.
  x0[-1]=max(0,float((floor-h0)[gid==0].max()));pt=p0.copy();rt=r0.copy()
  for body in effectors:pt[body,2]+=max(0,float((floor-h0)[gid==body].max()))
  weights=np.ones(15)*2;weights[effectors]=400
  target_offset=previous_offset if previous_offset is not None else np.zeros(35)
  def objective(x):
   p,r,_=decode(x,frame)
   return float(((p-pt)**2*weights[:,None]).sum()+.07*((r-rt)**2).sum()+.008*((x[:-1]-x0[:-1])**2).sum()+2000*(x[-1]-x0[-1])**2+.015*((x-x0-target_offset)**2).sum())
  def constraints(x):
   p,r,_=decode(x,frame)
   return np.r_[heights(p,r)-floor,[1-x[a+1]**2-x[a+2]**2 for a in ball_starts]]
  initial=x0.copy()
  if previous_offset is not None:initial=np.clip(x0+.6*previous_offset,bounds[:,0],bounds[:,1])
  opt=minimize(objective,initial,method='SLSQP',bounds=bounds,constraints=[dict(type='ineq',fun=constraints)],options=dict(maxiter=180,ftol=1e-10))
  if min(constraints(opt.x))< -2e-6:raise RuntimeError((f,opt.message,float(min(constraints(opt.x)))))
  p,r,dof=decode(opt.x,frame);row=np.r_[frame[:6],dof];row[2]+=opt.x[-1];result.append(row)
  previous_offset=opt.x-x0
  stats.append(dict(frame=f,iterations=opt.nit,root_lift_m=float(opt.x[-1]),minimum_clearance_m=float(heights(p,r).min()),hand_target_error_m=np.linalg.norm(p[hands]-pt[hands],axis=1).tolist()))
  if f%10==0:print('frame',f,'iterations',opt.nit,'root lift',round(opt.x[-1],4),flush=True)
 return np.array(result,dtype=np.float32),stats

def fk(frames):
 roots=torch.tensor(frames[:,:3],dtype=torch.float32);rot=torch.tensor(R.from_rotvec(frames[:,3:6]).as_quat(),dtype=torch.float32)
 p,q=model.forward_kinematics(roots,rot,model.dof_to_rot(torch.tensor(frames[:,6:],dtype=torch.float32)))
 return p.numpy(),q.numpy()

def main():
 preview=json.loads((ROOT/'Saved/MimicKitEquipment/recovery-preview/data.json').read_text());report=[]
 for side in ('front','back'):
  path=ROOT/f'Saved/MimicKitEquipment/package/motions/recovery/getUp_{side}_quick_robotic.pkl';data=pickle.loads(path.read_bytes())
  cleanpath=OUT/f'getUp_{side}_quick_clean.pkl'
  if cleanpath.exists() and '--reuse' in sys.argv:cleaned=pickle.loads(cleanpath.read_bytes())['frames'];stats=[]
  else:
   print('Cleaning',side,flush=True);cleaned,stats=clean(data['frames']);cleanpath.write_bytes(pickle.dumps(dict(data,frames=cleaned)))
  bad=[]
  for j in meta['joints']:
   v,_=sampled_coordinates(model,j,cleaned,8)
   if violation(v,j).any():bad.append(dict(body=j['body'],count=int(violation(v,j).sum())))
  p,q=fk(cleaned);clip=next(c for c in preview['clips'] if side in c['id'])
  pose=np.concatenate([p,q],-1);pose[:,:,:2]-=p[0,0,:2].copy();clip['original_poses']=clip['poses'];clip['poses']=pose.tolist();clip.pop('reset_poses',None)
  clip['label']='Get up · '+side+' · cleaned';clip['cleaned']=True
  report.append(dict(clip=side,source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),frames=len(cleaned),stats=stats,limit_violations_240hz=bad))
  print('Finished',side,'limit violations',bad,flush=True)
 (OUT/'data.json').write_text(json.dumps(preview,separators=(',',':')));(OUT/'report.json').write_text(json.dumps(report,indent=2))
if __name__=='__main__':main()
