"""Replay captured live UE inputs through the original Python Dodge policy."""
import json,sys,dataclasses
from pathlib import Path
import numpy as np
import torch
sys.path.insert(0,r'C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/ParryAndDodge/temp_dodge_reference_viz')
import inference as m
from dodge_banked_agent import BankState
import transition_features as features
p=Path(__file__).parent
engine=m.Engine()
native_geometry='--native-geometry' in sys.argv
if native_geometry:
 fixture=torch.load(m.BASE/'reference/fixture.pt',map_location='cpu',weights_only=False)
 folder=engine.folder/'native_geometry';folder.mkdir()
 engine.skeleton,_=m.build_runtime(fixture,folder,'cpu')
agent=m.load_policy(engine.checkpoint,engine.skeleton,['walk'],['hookL'],'cpu')
def t(v):return torch.tensor(v,dtype=torch.float32)[None]
def state(s):
 pr=t(s['previous_root']);cr=t(s['current_root'])
 return BankState(t(s['previous_lower']),t(s['previous_upper']),t(s['current_lower']),t(s['current_upper']),
  pr[:,:3],pr[:,3:].reshape(1,3,3),cr[:,:3],cr[:,3:].reshape(1,3,3),pr[:,3:].reshape(1,3,3),
  t(s['initial_delta_world']),t([s['initial_delta_yaw']]),t(s['remaining']),t(s['root_shift']),t([s['yaw_offset']]))
def err(a,b):return float(np.max(np.abs(np.asarray(a).reshape(-1)-np.asarray(b).reshape(-1))))
records=[]
with torch.inference_mode():
 for file in sorted((p/'NativeTrace').glob('continue_*_upper.json')):
  d=json.loads(file.read_text());lo=json.loads(file.with_name(file.name.replace('_upper','_lower')).read_text());s=state(d['before'])
  agent.category.fill_(lo['category']);seen={}
  hooks=[]
  for kind in ['walk','run']:
   hooks.append(agent.frozen.models[kind].register_forward_pre_hook(lambda module,args,k=kind:seen.update({k:args[0].clone()})))
  baseline,pins=agent.frozen(s,agent.category)
  for hook in hooks:hook.remove()
  key='run' if lo['category'] else 'walk'
  r=dict(file=file.name,lower_input_error=err(seen[key],lo['input']),lower_clean_error=err(baseline,lo['cleaned']),
    ue_future=lo['input'][120:],python_future=seen[key][0,120:].tolist())
  hf=agent.frozen.register_forward_hook(lambda module,args,out:(t(lo['cleaned']),t(lo['pins'])))
  hu=agent.upper.register_forward_pre_hook(lambda module,args:seen.update(upper_input=args[0].clone()))
  ho=agent.upper.register_forward_hook(lambda module,args,out:seen.update(upper_output=out[0].clone()))
  old=features.conditioning
  def condition(*args):
   a=list(args);root=t(d['planned_root']);axes=root[:,3:].reshape(1,3,3)
   a[5]=root[:,:3]-s.current_root
   before=torch.atan2(-s.current_axes[:,1,0],-s.current_axes[:,1,2]);after=torch.atan2(-axes[:,1,0],-axes[:,1,2])
   delta=after-before;a[6]=torch.atan2(torch.sin(delta),torch.cos(delta))[:,None]
   return old(*a)
  features.conditioning=condition
  pelvis=t(d['pelvis']).reshape(1,2,9);collider=t(d['collider']).reshape(1,2,9)
  try:
   proposal=agent(s,pelvis[:,0],pelvis[:,1],collider[:,0],collider[:,1],t([d['event']]),t(d['target']),t(d['attack_controls']+[0]))
  finally:
   features.conditioning=old;hf.remove();hu.remove();ho.remove()
  r.update(upper_input_error=err(seen['upper_input'],d['input']),upper_output_error=err(seen['upper_output'],d['output']),
    position_error_cm=100*err(proposal.positions,d['positions']),rotation_error=err(proposal.rotations,d['rotations']))
  r['bone_errors_cm']={name:float(value) for name,value in zip(engine.skeleton.body_names,np.linalg.norm(proposal.positions[0].numpy()-np.asarray(d['positions']).reshape(25,3),axis=1)*100)}
  if len(records)==0:
   print('BONE ERRORS',r['bone_errors_cm'],flush=True)
   print('UE initial lower',d['before']['current_lower'][:9],'fixture',engine.fixture['episode']['lower_primers'][0,1,:9].tolist(),flush=True)
   print('UE planned/current',d['planned_root'],d['before']['current_root'],flush=True)
  records.append(r);print({k:v for k,v in r.items() if not k.endswith('future') and k!='bone_errors_cm'},flush=True)
(p/('native_geometry_replay.json' if native_geometry else 'native_replay.json')).write_text(json.dumps(records,indent=2))
