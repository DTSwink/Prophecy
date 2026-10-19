"""Contact-interval hand IK; original pelvis trajectory, unchanged PHAT."""
from clean_recovery_preview import *
PIN={'front':{'right':(6,18),'left':(6,12)},'back':{'right':(10,16),'left':(10,12)}}
DEST=ROOT/'Saved/MimicKitEquipment/recovery-pinned-preview';DEST.mkdir(exist_ok=True)

def smooth(t):return t*t*t*(10+t*(-15+6*t))

def solve_pair(base,frame,targets,previous):
 chosen=[e for e in entries if e['j']['body'] in ['torso']+[s+'_'+p for s in ('right','left') for p in ('upper_arm','lower_arm','hand')]]
 indices=np.concatenate([np.arange(e['start'],e['start']+(3 if e['j']['kind']=='ball' else 1)) for e in chosen]);seed=base[indices]
 oldp,oldr,_=decode(base,frame);floor0=heights(oldp,oldr)
 def unpack(z):x=base.copy();x[indices]=z;return x
 def objective(z):
  p,r,_=decode(unpack(z),frame);value=.02*np.sum((z-seed)**2)+.3*np.sum((r[1]-oldr[1])**2)
  for body,pt,rt,pin in targets:value+=80*np.sum((p[body]-pt)**2)+.3*np.sum((r[body]-rt)**2)
  if previous is not None:value+=.025*np.sum((z-previous)**2)
  return value
 def equal(z):
  p,r,_=decode(unpack(z),frame)
  return np.concatenate([p[b]-pt for b,pt,rt,pin in targets if pin])
 def constraints(z):
  x=unpack(z);p,r,_=decode(x,frame);h=heights(p,r)
  return np.r_[[1-x[e['start']+1]**2-x[e['start']+2]**2 for e in chosen if e['j']['kind']=='ball'],h[np.isin(gid,hands)]-.002,h[np.isin(gid,[1,2])]-np.minimum(floor0[np.isin(gid,[1,2])],.002)]
 cons=[dict(type='ineq',fun=constraints)]
 if any(t[3] for t in targets):cons.append(dict(type='eq',fun=equal))
 initial=seed if previous is None else np.clip(previous,bounds[indices,0],bounds[indices,1])
 res=minimize(objective,initial,method='SLSQP',bounds=bounds[indices],constraints=cons,options=dict(maxiter=220,ftol=1e-10))
 err=max(abs(equal(res.x))) if any(t[3] for t in targets) else 0
 if err>2e-4 or min(constraints(res.x))< -1e-6:raise RuntimeError(dict(error_m=float(err),constraint=float(min(constraints(res.x))),message=res.message))
 return unpack(res.x),res.x

def main():
 preview=json.loads((OUT/'data.json').read_text());reports=[]
 for clipname in ('front','back'):
  path=ROOT/f'Saved/MimicKitEquipment/package/motions/recovery/getUp_{clipname}_quick_robotic.pkl';source=pickle.loads(path.read_bytes());original=source['frames']
  old=pickle.loads((OUT/f'getUp_{clipname}_quick_clean.pkl').read_bytes())['frames']
  frames=old.copy();frames[:,:6]=original[:,:6]
  bases=np.array([encode(f) for f in frames]);poses=[decode(x,f) for x,f in zip(bases,frames)]
  hand_reports=[];alltargets=[[] for f in frames]
  for side,(lo,hi) in PIN[clipname].items():
   body=names.index(side+'_hand');shape=next(s for s in shapes if s[0]==body)
   pp=np.array([v[0][body] for v in poses]);rr=np.array([v[1][body] for v in poses]);middle=(lo+hi)//2
   anchor_r=rr[middle];anchor_p=np.median(pp[lo:hi+1],0)
   fakep=poses[middle][0].copy();faker=poses[middle][1].copy();fakep[body]=anchor_p;faker[body]=anchor_r
   anchor_p[2]+=.003-heights(fakep,faker)[gid==body].min()
   print('pin',clipname,side,lo,hi,'anchor',anchor_p.tolist(),flush=True)
   for f in range(len(frames)):
    blend=smooth(np.clip((f-(lo-5))/5,0,1))*smooth(np.clip(((hi+5)-f)/5,0,1))
    target_p=(1-blend)*pp[f]+blend*anchor_p
    target_r=Slerp([0,1],R.from_matrix(np.array([rr[f],anchor_r])))([blend]).as_matrix()[0]
    fp=poses[f][0].copy();fr=poses[f][1].copy();fp[body]=target_p;fr[body]=target_r
    target_p[2]+=max(0,.003-heights(fp,fr)[gid==body].min())
    alltargets[f].append((body,target_p,target_r,lo<=f<=hi))
   hand_reports.append(dict(side=side,start_frame=lo,end_frame=hi,anchor_position=anchor_p.tolist(),anchor_rotation=R.from_matrix(anchor_r).as_quat().tolist()))
  previous=None
  for f in range(len(frames)):
   try:bases[f],previous=solve_pair(bases[f],frames[f],alltargets[f],previous)
   except RuntimeError as error:raise RuntimeError((clipname,f,str(error)))
   if f%10==0:print('solved',clipname,f,flush=True)
  for i,(x,f) in enumerate(zip(bases,frames)):frames[i,6:]=decode(x,f)[2]
  np.testing.assert_array_equal(frames[:,:6],original[:,:6])
  dest=DEST/f'getUp_{clipname}_quick_pinned.pkl';dest.write_bytes(pickle.dumps(dict(source,frames=frames)))
  p,q=fk(frames);row=next(c for c in preview['clips'] if clipname in c['id']);pose=np.concatenate([p,q],-1);pose[:,:,:2]-=p[0,0,:2];row['poses']=pose.tolist();row['label']='Get up · '+clipname+' · planted hands'
  reports.append(dict(clip=clipname,hands=hand_reports,pelvis_exact=True));(DEST/'report.json').write_text(json.dumps(reports,indent=2))
 (DEST/'data.json').write_text(json.dumps(preview,separators=(',',':')))
if __name__=='__main__':main()
