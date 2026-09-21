import sys,json,dataclasses
from pathlib import Path
import numpy as np
import torch
sys.path.insert(0,r'C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/ParryAndDodge/temp_dodge_reference_viz')
import inference as m
from transition_rollout import Episode,rollout
p=Path(__file__).parent
engine=m.Engine()
native_geometry='--native-geometry' in sys.argv
if native_geometry:
 fixture=torch.load(m.BASE/'reference/fixture.pt',map_location='cpu',weights_only=False)
 folder=engine.folder/'native_geometry';folder.mkdir();engine.skeleton,_=m.build_runtime(fixture,folder,'cpu')
agent=m.load_policy(engine.checkpoint,engine.skeleton,['walk'],['hookL'],'cpu')
traces={int(f.name.split('_')[-2]):json.loads(f.read_text()) for f in (p/'NativeTrace').glob('continue_*_upper.json')}
first=traces[min(traces)];seed=first['before']
data=json.loads((p/'updated_viewer_82.json').read_text());view=data['rollout'];attack=data['attacker'];names=attack['names']
ep=dict(engine.fixture['episode']);N=len(view['positions']);ap=np.asarray(attack['positions'],np.float32);ar=np.asarray(attack['basis'],np.float32);pi=names.index('pelvis')
vals=dict(pelvis=np.concatenate([ap[:,pi],ar[:,pi,:2].reshape(N,6)],-1),collider=view['attack_collider'],collider_axes=view['attack_collider_axes'],
 event=(np.arange(N)>=data['scenario']['hit_frame']).astype(np.float32)[:,None],times=np.arange(N,dtype=np.float32),
 target_world=view['target_world'],attack_half=view['attack_half'],attack_type=m.attack_labels('hookL'))
for key,v in vals.items():ep[key]=torch.tensor(np.asarray(v,np.float32))[None]
ep['valid']=torch.ones((1,N),dtype=torch.bool)
e=Episode(**ep,authored_roots=None)
def crop(e,start):return dataclasses.replace(e,**{k:getattr(e,k)[:,start:] for k in ['pelvis','collider','collider_axes','event','times','valid']})
start=min(traces)-2
e=crop(e,start)
def tensor(x):return torch.tensor(np.asarray(x),dtype=torch.float32)[None]
ue_seed=dict(lower_primers=tensor([seed['previous_lower'],seed['current_lower']]),upper_primers=tensor([seed['previous_upper'],seed['current_upper']]))
ue_axes=np.asarray(seed['current_root'][3:],np.float32).reshape(3,3);view_root=e.root_primers[0,1].numpy();view_axes=view_root[3:].reshape(3,3)
rotation=ue_axes.T@view_axes
def rebase(value):
 v=np.asarray(value,np.float32).copy();v[:3]=(v[:3]-np.asarray(seed['current_root'][:3]))@rotation+view_root[:3]
 v[3:]= (v[3:].reshape(2,3)@rotation).reshape(6);return v
pelvis=[];collider=[];events=[]
for frame in range(start,N):
 src=first if frame<=min(traces) else traces[frame];sample=0 if frame<min(traces) else 1
 pelvis.append(rebase(src['pelvis'][sample*9:sample*9+9]));collider.append(rebase(src['collider'][sample*9:sample*9+9]));events.append([src['event'] if frame>=min(traces) else 0])
ue_attack=dict(pelvis=tensor(pelvis),collider=tensor(collider),event=tensor(events),
 target_world=tensor((np.asarray(first['target'])-np.asarray(seed['current_root'][:3]))@rotation+view_root[:3]))
results={}
with torch.inference_mode():
 for seedname,changes1 in [('viewer',{}),('ue',ue_seed),('ue_upper',{'upper_primers':ue_seed['upper_primers']}),('ue_lower',{'lower_primers':ue_seed['lower_primers']})]:
  for attackname,changes2 in [('viewer',{}),('ue',ue_attack)]:
   x=dataclasses.replace(e,**changes1,**changes2);a=rollout(agent,x)
   h=a.positions[0,:,engine.skeleton.body_names.index('head')].numpy()*100
   key=seedname+'_seed_'+attackname+'_attack'
   results[key]=dict(head=h.tolist(),delta=(h-h[1]).tolist(),positions=a.positions[0].tolist(),basis=a.rotations[0].tolist())
   if key=='ue_seed_ue_attack':
    errors=[]
    for frame in range(min(traces),N):
     expected=np.asarray(traces[frame]['positions']).reshape(25,3)@rotation+view_root[:3]
     errors.append(float(np.max(np.linalg.norm(a.positions[0,frame-start].numpy()-expected,axis=1))*100))
    print('UE FULL RECURRENCE BONE ERRORS CM',errors,flush=True)
    results[key]['ue_error_cm']=errors
   print(key,'head delta at attack frame8',np.round(h[8-start]-h[1],2),'at frame11',np.round(h[-1]-h[1],2),flush=True)
(p/f'input_isolation_first{min(traces)}{"_native" if native_geometry else ""}.json').write_text(json.dumps(results))
print('initial pelvis UE/viewer',ue_seed['lower_primers'][0,1,:9].tolist(),e.lower_primers[0,1,:9].tolist())
print('targets in root UE/viewer',((ue_attack['target_world'][0]-e.root_primers[0,1,:3])@e.root_primers[0,1,3:].reshape(3,3).T).tolist(),((e.target_world[0]-e.root_primers[0,1,:3])@e.root_primers[0,1,3:].reshape(3,3).T).tolist())
