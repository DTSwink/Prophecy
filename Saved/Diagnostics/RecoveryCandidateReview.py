"""Frozen-input geometric candidate comparison; not a closed-loop rollout."""
import os
os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
import json,pathlib,sys,numpy as np
from scipy.spatial.transform import Rotation
root=pathlib.Path(__file__).resolve().parents[2]
run=json.loads((root/'Content/locomotion/NN/prophecy_lower_body_runtime.json').read_text())
walk=json.loads((root/'Content/locomotion/NN/prophecy_lower_body_walk_july5_runtime.json').read_text())
off=np.array(run['local_offsets_m']);roll=run['foot_roll']
rows={round(r['time']*60):r for r in map(json.loads,(root/'Saved/Diagnostics/PelvisHitch-20260920-193832/pipeline.jsonl').read_text().splitlines()) if r['actor'].endswith('_C_1')}
def unit(v):return np.asarray(v)/max(1e-12,np.linalg.norm(v))
def project(v,a):return unit(v-a*np.dot(v,a))
def rot(v):
 x=unit(v[:3]);y=project(v[3:],x);return np.array([x,y,np.cross(x,y)])
def aa(axis,angle):return Rotation.from_rotvec(unit(axis)*angle).as_matrix().T
def angle(a,b):return float(np.degrees(Rotation.from_matrix(a@b.T).magnitude()))
def blend(a,b,w):
 return a@Rotation.from_rotvec(Rotation.from_matrix((a.T@b).T).as_rotvec()*w).as_matrix().T
def smooth(x):x=np.clip(x,0,1);return x*x*(3-2*x)
def clearance(s,i):
 o=9+16*i;r=rot(s[o+3:o+9]);toe=s[o:o+3]+np.array(walk['ik_toe_offsets_m'][i])@r
 fw=r[1].copy();up=r[0].copy();side=r[2]
 if np.dot(fw,toe-s[o:o+3])<0:fw=-fw
 if up[2]<0:up=-up
 dims=np.array(roll['foot_half_dims_m']);tdims=np.array(roll['toe_half_dims_m']);sole=roll['sole_vertical_offset_m']
 center=toe-fw*dims[0]+up*sole
 tr=aa(walk['ik_toe_axes'][i],np.clip(s[o+15],-1,1)*run['ik_toe_alpha_rad'])@r
 tf=tr[0].copy();tu=tr[1].copy();ts=tr[2]
 if np.dot(tf,toe-s[o:o+3])<0:tf=-tf
 if tu[2]<0:tu=-tu
 tc=toe+tf*tdims[0]+tu*sole
 return min(center[2]-np.dot(np.abs([fw[2],side[2],up[2]]),dims),tc[2]-np.dot(np.abs([tf[2],ts[2],tu[2]]),tdims))-roll['ground_y']-1e-5
def solve(src,target,i):
 o=9+16*i;h=17+4*i;k=off[h+1];L1=np.linalg.norm(k);L2=np.linalg.norm(off[h+2])
 oldr=rot(src[o+9:o+15]);oldhip=src[:3]+off[h]@rot(src[3:9]);oldupper=k@oldr
 oldaxis=unit(src[o:o+3]-oldhip);oldpole=project(oldupper,oldaxis)
 hip=target[:3]+off[h]@rot(target[3:9]);axis=unit(target[o:o+3]-hip)
 carried=project(oldpole-(oldaxis+axis)*np.dot(oldpole,axis)/max(1e-6,1+np.dot(oldaxis,axis)),axis)
 d=min(np.linalg.norm(target[o:o+3]-hip),L1+L2-2e-5);along=(L1*L1-L2*L2+d*d)/(2*d)
 upper=axis*along+carried*np.sqrt(max(0,L1*L1-along*along))
 oldn=unit(np.cross(oldaxis,oldpole));newn=unit(np.cross(axis,carried))
 oldbasis=np.array([unit(oldupper),unit(np.cross(oldn,unit(oldupper))),oldn]);newbasis=np.array([unit(upper),unit(np.cross(newn,unit(upper))),newn])
 return oldr@oldbasis.T@newbasis,axis,carried
def guidance(m,target,i,weight=1):
 o=9+16*i;h=17+4*i;hip=target[:3]+off[h]@rot(target[3:9]);axis=unit(target[o:o+3]-hip)
 toe=unit(walk['ik_toe_offsets_m'][i])@rot(target[o+3:o+9]);flat=toe*[1,1,0];side=np.cross([0,0,1],unit(flat));upper=off[h+1]@m
 along=np.dot(upper,axis);radial=upper-axis*along;R=np.linalg.norm(radial);pole=unit(radial);sn=np.dot(side,axis);n0=side-axis*sn;nl=np.linalg.norm(n0);n=unit(n0)
 q=-along*sn/max(1e-12,R*nl);strength=smooth(np.dot(flat,flat)*4)*smooth(nl*nl*4)*smooth((1-abs(q))*4)*weight
 desired=n*np.clip(q,-1,1)+unit(np.cross(axis,n))*np.sqrt(max(0,1-np.clip(q,-1,1)**2))
 turn=np.arctan2(np.dot(axis,np.cross(pole,desired)),np.clip(np.dot(pole,desired),-1,1))*strength
 return m@aa(axis,turn)
def pole_blend(p,n,axis,k,w):
 pa=project(k@p,axis);pb=project(k@n,axis)
 turn=np.arctan2(np.dot(axis,np.cross(pa,pb)),np.clip(np.dot(pa,pb),-1,1))
 aligned=p@aa(axis,turn)
 # Remaining orientation difference is twist around the now-common upper bone.
 residual=Rotation.from_matrix((aligned.T@n).T).as_rotvec()
 twist=np.dot(residual,unit(k@n))
 tilted=p@aa(axis,turn*w);upper=unit(k@tilted)
 return tilted@aa(upper,twist*w),float(np.degrees(turn)),float(np.degrees(twist))

out=[];variations={};maxreplay=0
for t in range(151,178,2):
 r=rows[t];target=np.array(r['published_lower']);prev=np.array(r['previous_lower']);raw=np.array(r['lower_input'][:41])+r['lower_delta'][:41]
 record={'tick':t,'legs':{}}
 variants={k:target.copy() for k in ['guidance_fade','hybrid_source_fade','hybrid_source_guidance','pole_source_fade','pole_source_guidance']}
 for i,side in enumerate(('left','right')):
  o=9+16*i;k=off[18+4*i];cl=clearance(target,i);w=1-smooth((cl-.02)/.10)
  old,axis,_=solve(prev,target,i);nn,_,_=solve(raw,target,i);accepted=guidance(old,target,i)
  maxreplay=max(maxreplay,angle(accepted,rot(target[o+9:o+15])))
  hybrid=prev.copy()
  for q in (0,o):hybrid[q:q+3]=prev[q:q+3]*(1-w)+raw[q:q+3]*w
  for q in (3,o+9):hybrid[q:q+6]=blend(rot(prev[q:q+6]),rot(raw[q:q+6]),w)[:2].ravel()
  hm,_,_=solve(hybrid,target,i);pm,turn,twist=pole_blend(old,nn,axis,k,w)
  candidates={'guidance_fade':guidance(old,target,i,1-w),'hybrid_source_fade':guidance(hm,target,i,1-w),'hybrid_source_guidance':guidance(hm,target,i),'pole_source_fade':guidance(pm,target,i,1-w),'pole_source_guidance':guidance(pm,target,i)}
  checks={}
  hip=target[:3]+off[17+4*i]@rot(target[3:9])
  for name,m in candidates.items():
   variants[name][o+9:o+15]=m[:2].ravel()
   checks[name]={'from_accepted_deg':angle(accepted,m),'from_raw_deg':angle(rot(raw[o+9:o+15]),m),'from_prev_deg':angle(rot(prev[o+9:o+15]),m),'calf_length_error_cm':float(abs(np.linalg.norm(target[o:o+3]-hip-k@m)-np.linalg.norm(off[19+4*i]))*100)}
  record['legs'][side]={'clearance_cm':float(cl*100),'support':float(w),'raw_pole_turn_deg':turn,'raw_twist_deg':twist,'candidates':checks}
 for name,s in variants.items():
  x=np.array(rows[t+2]['lower_input']);v=x.copy()
  for o in (18,34):
   carry=rot(target[o:o+6]).T@rot(x[o:o+6]);v[o:o+6]=(rot(s[o:o+6])@carry)[:2].ravel();v[o+76:o+82]=(v[o:o+6]-v[o+41:o+47])/walk['pose_delta_scale_final']
  variations[t,name]=v
 out.append(record)

import torch
torch.set_num_threads(1);torch.set_num_interop_threads(1)
sys.path.insert(0,r'C:\Users\singerie\Documents\Cursor\stepper')
from training.ik import ik_core as tl,visualize
cp=torch.load(walk['checkpoint_path'],map_location='cpu',weights_only=False);visualize.apply_simple_controller_policy(cp)
cfg=tl.TrainConfig();visualize.apply_config_dict(cfg,cp['config']);clip=tl.MotionClip(pathlib.Path(walk['seed_clip_path']),cfg,cyclic_animation=True)
model=visualize.load_model(cp,clip,cfg,torch.device('cpu')).eval()
with torch.inference_mode():ys=model(torch.tensor(np.array(list(variations.values())),dtype=torch.float32)).numpy()
predictions={key:y for key,y in zip(variations,ys)}
for rec in out:
 t=rec['tick'];rec['next_pelvis_delta_cm']={'accepted':(np.array(rows[t+2]['lower_delta'][:3])*100).tolist(),**{name:(y[:3]*100).tolist() for (tick,name),y in predictions.items() if tick==t}}
result={'warning':'Frozen-input, one-step interventions. No closed-loop rollout; candidate endpoint fixed to baseline.','max_baseline_replay_error_deg':maxreplay,'records':out}
dest=root/'Saved/Diagnostics/RecoveryCandidateReview.json';dest.write_text(json.dumps(result,indent=2))
print('REPLAY_ERROR_DEG',maxreplay,'SAVED',dest)
for r in out:
 print(r['tick'],[(side,round(x['clearance_cm'],3),round(x['support'],3),round(x['raw_pole_turn_deg'],2)) for side,x in r['legs'].items()], {k:round(v[0],3) for k,v in r['next_pelvis_delta_cm'].items()})
