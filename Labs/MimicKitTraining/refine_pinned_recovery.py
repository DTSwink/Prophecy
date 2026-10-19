"""Bake contact IK at 120 Hz to remove joint-interpolation hand drift."""
from pin_recovery_hands import *
from anim.motion_lib import MotionLib
import yaml

manifest=DEST/'motions.yaml'
lib=MotionLib(str(manifest),model,'cpu')
reports=json.loads((DEST/'report.json').read_text())
preview=json.loads((DEST/'data.json').read_text())
chosen=[e for e in entries if e['j']['body'] in ['torso']+[s+'_'+p for s in ('right','left') for p in ('upper_arm','lower_arm','hand')]]
indices=np.concatenate([np.arange(e['start'],e['start']+(3 if e['j']['kind']=='ball' else 1)) for e in chosen])
for i,side in enumerate(('front','back')):
 path=DEST/f'getUp_{side}_quick_pinned.pkl';source=pickle.loads(path.read_bytes())
 (DEST/f'getUp_{side}_30fps.pkl').write_bytes(path.read_bytes())
 duration=float(lib.get_motion_length(i));n=round(duration*120)+1
 times=torch.linspace(0,duration,n);ids=torch.full((n,),i,dtype=torch.long)
 root,rot,vel,ang,joints,dof=lib.calc_motion_frame(ids,times)
 frames=np.c_[root.numpy(),R.from_quat(rot.numpy()).as_rotvec(),lib.joint_rot_to_dof(joints).numpy()]
 for f,frame in enumerate(frames):
  base=encode(frame);oldp,oldr,_=decode(base,frame);floor0=heights(oldp,oldr)
  pins=[(names.index(h['side']+'_hand'),np.array(h['anchor_position'])) for h in reports[i]['hands'] if h['start_frame']*4<=f<=h['end_frame']*4]
  if f%4==0 or (not pins and floor0[np.isin(gid,hands)].min()>=.0015):continue
  seed=base[indices]
  def unpack(z):x=base.copy();x[indices]=z;return x
  def equal(z):
   p,r,_=decode(unpack(z),frame);return np.concatenate([p[b]-pt for b,pt in pins])
  def inequality(z):
   x=unpack(z);p,r,_=decode(x,frame);h=heights(p,r)
   return np.r_[[1-x[e['start']+1]**2-x[e['start']+2]**2 for e in chosen if e['j']['kind']=='ball'],h[np.isin(gid,hands)]-.0015]
  constraints=[dict(type='ineq',fun=inequality)]
  if pins:constraints.append(dict(type='eq',fun=equal))
  res=minimize(lambda z:np.sum((z-seed)**2),seed,jac=lambda z:2*(z-seed),method='SLSQP',bounds=bounds[indices],constraints=constraints,options=dict(maxiter=80,ftol=1e-11))
  if min(inequality(res.x))< -1e-6 or (pins and max(abs(equal(res.x)))>1e-5):raise RuntimeError((side,f,res.message))
  frames[f,6:]=decode(unpack(res.x),frame)[2]
 path.write_bytes(pickle.dumps(dict(source,frames=frames,fps=120)))
 # Preview still uses the original 30 Hz timeline; show the same authored samples.
 reports[i]['baked_fps']=120
 print(side,'baked',n,'frames',flush=True)
(DEST/'report.json').write_text(json.dumps(reports,indent=2))
