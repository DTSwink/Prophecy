import runpy
g=runpy.run_path(str(__import__('pathlib').Path(__file__).with_name('CompareTurnLower.py')))
globals().update({k:v for k,v in g.items() if not k.startswith('__')})
lc.FOOT_ROLL_INTEGRATION_STEPS=4
with torch.inference_mode():
 expected=lc.clean_output_vector(raw,runtime.store,x[:,:41],x[:,41:82]);print('MATCHED FOUR STEPS error',float((expected-actual).abs().max()),flush=True)
 uppermodel=ctl.UpperCachedLowerAgent();uppermodel.load_state_dict(uppercp['model']);uppermodel.eval()
 rest=runtime.rest_offsets_by_mode[1.][0];full=runtime.full_by_mode[1.]
 def mkbase(pel):
  rot=tl.rotation_6d_to_matrix(pel[:,3:]);parts=[torch.tensor([1.,0,0,0,1,0]).repeat(len(pel),10)]
  for name in ['hand_l','hand_r']:
   hp=(rest[full.body_names.index(name)][None,None,:]@rot).squeeze(1)+pel[:,:3];parts.extend([hp,pel[:,3:],pel[:,3:]])
  return ud.clean_upper_state(torch.cat(parts,-1))
 def heading_transform(state,p,r):return torch.cat([state[:,p:p+3]@seed,tl.rotmat_to_6d(tl.rotation_6d_to_matrix(state[:,r:r+6])@seed)],-1)
 def rebase(state,dyaw):
  a=torch.as_tensor(dyaw);bridge=torch.eye(3);bridge[0,0]=a.cos();bridge[0,2]=a.sin();bridge[2,0]=-a.sin();bridge[2,2]=a.cos();bridge=seed@bridge@seed.T
  out=state.clone()
  for p in [0,9,25]:out[:,p:p+3]=state[:,p:p+3]@bridge
  for r in [3,12,18,28,34]:out[:,r:r+6]=tl.rotmat_to_6d(tl.rotation_6d_to_matrix(state[:,r:r+6])@bridge)
  return out
 for name,steps in [('oracle',4),('authored4',4),('authored60',60)]:
  lc.FOOT_ROLL_INTEGRATION_STEPS=steps
  inputs=x.clone();rootfeatures=torch.tensor(u['inputs'])[:,207:242].clone();use_roots=rootinfo.clone()
  original_yaw=rootinfo[:,11].numpy();turn_starts=np.where((abs(np.diff(original_yaw))>1e-6)&(np.r_[True,abs(np.diff(original_yaw)[:-1])<1e-6]))[0]
  if name.startswith('authored'):
   authored=np.load(base/'viewer_holding_sword_npz.npz')['root_rotations'];rel=authored[0].T@authored;profile=np.unwrap(np.arctan2(rel[:,2,0],rel[:,2,2]))
   trajectory=np.zeros(len(rows)+10,dtype=np.float32)
   for start in turn_starts:
    count=len(trajectory)-start;trajectory[start:]+=np.pad(profile,(0,max(0,count-len(profile))),mode='edge')[:count]
  else:trajectory=np.r_[original_yaw,np.repeat(original_yaw[-1],10)]
  for i in range(len(rows)):
   use_roots[i,11]=float(trajectory[i]);use_roots[i,3]=float(trajectory[i]);use_roots[i,7]=float(trajectory[i+1])
   rootfeatures[i,2]=float((trajectory[i]-trajectory[max(0,i-1)])/cfg.max_turn_rate_scale_final)
   for k in range(8):
    d=float(trajectory[i+k+1]-trajectory[i]);rootfeatures[i,3+k*4:7+k*4]=torch.tensor([0.,0.,np.cos(d),np.sin(d)])
  inputs[:,117:]=rootfeatures
  current=x[:1,:41].clone();previous=x[:1,41:82].clone();ux=torch.tensor(u['inputs']);uprev=ux[:1,:90].clone();ucur=torch.tensor([rows[0]['previous_upper']]);pprev=ux[:1,180:189].clone();pcur=ux[:1,189:198].clone();basecur=mkbase(pcur)
  outlower=[];outupper=[];outpin=[]
  for i in range(min(360,len(x))):
   diff=(current-previous)/float(cfg.pose_delta_scale_final)
   inp=torch.cat([current,previous,diff[:,:3],diff[:,9:],inputs[i:i+1,117:]],-1)
   r=lc.model_raw_output(model,inp,current,runtime.store);transition,_,pin=lc.clean_output_vector_pair_with_pin_prob(r,runtime.store,current,previous)
   nextlower=rebase(transition,use_roots[i,7]-use_roots[i,11]);nextpelvis=heading_transform(nextlower,0,3);nextbase=mkbase(nextpelvis)
   prior=ud.clean_upper_state(nextbase+ucur-basecur)
   v=torch.cat([uprev,prior,pprev,pcur,nextpelvis,rootfeatures[i:i+1],ux[i:i+1,242:243],heading_transform(current,9,12),heading_transform(current,25,28),heading_transform(nextlower,9,12),heading_transform(nextlower,25,28),ux[i:i+1,279:]],-1)
   following=ud.clean_upper_state(prior+uppermodel(v));outlower.append(transition[0]);outupper.append(following[0]);outpin.append(pin[0])
   previous,current=current,nextlower;uprev,ucur=ucur,following;pprev,pcur=pcur,nextpelvis;basecur=nextbase
  outlower=torch.stack(outlower);outupper=torch.stack(outupper);print('autonomous',name,'lower error max',float((outlower-actual[:len(outlower)]).abs().max()),flush=True)
  np.savez(base/f'coupled_{name}.npz',lower=outlower.numpy(),upper=outupper.numpy(),pins=torch.stack(outpin).numpy(),roots=use_roots[:len(outlower)].numpy(),times=np.array([r['time'] for r in rows[:len(outlower)]]))
