import sys,json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import torch
from scipy.spatial.transform import Rotation as R
torch.set_num_threads(2)
sys.path.insert(0,'C:/Users/singerie/Documents/Cursor/stepper')
from training.ik import train_upper_pose_controller_pelvis as c
p=Path(__file__).parent;root=p.parents[2]
meta=json.loads((root/'Content/locomotion/NN/prophecy_upper_body_runtime.json').read_text())
cp=torch.load(meta['checkpoint_path'],map_location='cpu',weights_only=False)
model=c.UpperCachedLowerAgent();model.load_state_dict(cp['model']);model.eval()
def load(name):
 return {round(r['time']*60):r for r in map(json.loads,(p/(name+'-inputs.jsonl')).read_text().splitlines()) if r['actor']=='BP_ProphecyManualPoseAgent_C_0' and r['upper_inference']}
source_name=sys.argv[1] if len(sys.argv)>1 else 'baseline'
a=load(source_name);b=load('later_turn_stop')
def tensor(x):return torch.tensor(x,dtype=torch.float32).reshape(1,-1)
def clean(x):return c.upper_data.clean_upper_state(x)
def base(ph):
 rot=c.tl.rotation_6d_to_matrix(ph[:,3:9]);parts=[tensor([1,0,0,0,1,0]*10)]
 for spec in meta['arm_specs']:
  offset=tensor(meta['rest_offsets_from_pelvis_m'][spec['end']])
  pos=ph[:,:3]+(offset.unsqueeze(1)@rot).squeeze(1)
  parts.extend((pos,ph[:,3:9],ph[:,3:9]))
 return clean(torch.cat(parts,dim=1))
clip=SimpleNamespace(body_names=meta['body_names'],parents_body_list=meta['parents_body'],ik_limb_specs=[dict(s,kind='arm') for s in meta['arm_specs']])
offsets=torch.tensor(meta['local_offsets_m'],dtype=torch.float32)[None]
lengths=torch.tensor(meta['arm_limb_lengths_m'],dtype=torch.float32)[None]
def headrot(x):return R.from_matrix(c.tl.rotation_6d_to_matrix(x[:,42:48]).numpy()[0].T)
def yawmat(v):
 co,si=np.cos(v),np.sin(v)
 return np.array([[co,0,si],[0,1,0],[-si,0,co]])
def root_features(t):
 cur=np.array(a[t]['roots'][:4]);prev=np.array(a[t-2]['roots'][:4]);delta=(cur[:3]-prev[:3])@yawmat(prev[3]);out=[delta[0]*6,delta[2]*6,(cur[3]-prev[3])/(np.pi*24/180)]
 for k in range(1,9):
  future=np.array(a[t+2*k]['roots'][:4]);delta=(future[:3]-cur[:3])@yawmat(cur[3]);dy=future[3]-cur[3]
  out.extend([np.clip(delta[0]*6/k,-2,2),np.clip(delta[2]*6/k,-2,2),np.cos(dy),np.sin(dy)])
 return np.array(out,np.float32)
feature_errors=[]
for t in range(216,241,2):
 oracle=root_features(t);observed=np.array(a[t]['upper_input'][207:242]);d=oracle-observed
 feature_errors.append(dict(tick=t,current_max=float(abs(d[:3]).max()),future_position_max=float(abs(d[3:].reshape(8,4)[:,:2]).max()),future_yaw_vector_max=float(abs(d[3:].reshape(8,4)[:,2:]).max())))
print('Root feature errors',max(r['current_max'] for r in feature_errors),max(r['future_position_max'] for r in feature_errors),max(r['future_yaw_vector_max'] for r in feature_errors),flush=True)
results={}
for t in (216,220,228,236):
 x=tensor(a[t]['upper_input']);actual=clean(x[:,90:180]+tensor(a[t]['upper_delta']))
 history=tensor(a[t+4]['upper_input'][:90]);err=(actual-history).numpy()[0]
 expected_prior=clean(base(tensor(a[t+2]['upper_input'][198:207]))+history-base(tensor(a[t+2]['upper_input'][189:198])))
 priorerr=(expected_prior-tensor(a[t+2]['upper_input'][90:180])).numpy()[0]
 print('History audit',t,'output/history',[(i,round(float(err[i]),6)) for i in range(90) if abs(err[i])>1e-4],'prior error',float(abs(priorerr).max()),flush=True)
for start in (216,224):
 for mode in ('baseline','viewer_forearm_clamp','actual_future_roots','later_root_only','later_pelvis_only','later_feet_only','later_all_lower','gaze_zero'):
  prev=cur=None;rows=[]
  with torch.inference_mode():
   for t in range(start,253,2):
    x=tensor(a[t]['upper_input'])
    if cur is not None:
     x[:,:90]=prev
     x[:,90:180]=clean(base(x[:,198:207])+cur-base(x[:,189:198]))
    if mode=='actual_future_roots':x[:,207:242]=tensor(root_features(t))
    sections={'later_root_only':[(207,242)],'later_pelvis_only':[(180,207)],'later_feet_only':[(243,279)],'later_all_lower':[(180,242),(243,279)]}.get(mode,[])
    for lo,hi in sections:x[:,lo:hi]=tensor(b[t]['upper_input'][lo:hi])
    if mode=='gaze_zero':x[:,279:281]=0
    y=model(x);n=clean(x[:,90:180]+y)
    if mode=='viewer_forearm_clamp':n=c.clamp_viewer_forearm_lengths(clip,n,x[:,198:207],offsets,lengths)
    actual=tensor(a[t]['upper_input'][90:180])+tensor(a[t]['upper_delta']);actual=clean(actual)
    speed=np.degrees((headrot(x[:,90:180]).inv()*headrot(n)).magnitude())/2
    rows.append(dict(tick=t,head_deg_per_60hz_tick=float(speed),state_error=float(torch.max(torch.abs(n-actual))),head_error_deg=float(np.degrees((headrot(actual).inv()*headrot(n)).magnitude()))))
    # Current upper before this transition is recoverable from the baseline next
    # row's previous state for the first step. Subsequent rows use free recurrence.
    prev=tensor(a[t+2]['upper_input'][:90]) if cur is None else cur
    cur=n
  key=f'{start}_{mode}';results[key]=rows
  print(key,'max head speed',round(max(r['head_deg_per_60hz_tick'] for r in rows),4),'max state error',round(max(r['state_error'] for r in rows),7),flush=True)
(p/('recurrence-audit-'+source_name+'.json')).write_text(json.dumps(dict(source=source_name,feature_errors=feature_errors,rollouts=results),indent=2))
