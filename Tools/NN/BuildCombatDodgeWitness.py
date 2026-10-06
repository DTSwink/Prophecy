"""Rebuild the pinned October 5 full recurrent UE parity fixtures from local Stepper training assets. Run from the Prophecy project root."""
from pathlib import Path
import sys,json,gzip,copy
import numpy as np
import torch
BASE=Path('C:/Users/singerie/Documents/Cursor/stepper')
CODE=BASE/'training/slashes2/ParryAndDodge'
sys.path.insert(0,str(CODE))
from build_ue5_dodge_reference import build_runtime,tensor_tree
from dodge_banked_checkpoint import load_policy
from dodge_banked_inputs import HeightAttackBank,episode
from transition_rollout import rollout
from dataclasses import fields
torch.set_num_threads(1)
OUT=Path.cwd()/'Saved/Diagnostics/CombatParity20261005/dodge_witness';OUT.mkdir(parents=True,exist_ok=True)
saved=json.load(gzip.open(BASE/'training/runs/20261004_150744_dodge_bs256_unchanged_resume_8h/replayer/controller_step_00322975.json.gz','rt'))
old=torch.load(CODE/'training_packs_banked_v2/dodge_idle383_v1/dodge_idle383.pt',map_location='cpu',weights_only=False,mmap=True)
bank=HeightAttackBank(BASE/'training/runs/20261003_shared_defense_attacks_step184064')
cp=torch.load(BASE/'training/slashes2/saved_defense_checkpoints/20261004_150744_dodge_bs256_unchanged_resume_8h_step322925.pt',map_location='cpu',weights_only=False)
for row in (0,2,5):
 meta=saved['rows'][row];index=meta['clip_id'];entry=old['rows'][index];gid=int(old['geometry_ids'][index])
 folder=OUT/str(row);folder.mkdir(exist_ok=True)
 fixture=dict(prototype=old['prototype'],geometry={k:v[gid:gid+1].clone() for k,v in old['geometry'].items()},episode={k:v[index:index+1].clone() for k,v in old['episode'].items()})
 sk,_=build_runtime(fixture,folder,'cpu')
 template=json.load(open('Content/locomotion/NN/defense/dodge_skeleton.json'));template['geometry']={k:v.tolist() for k,v in fixture['geometry'].items()};(folder/'skeleton.json').write_text(json.dumps(template))
 rootp=np.asarray(saved['controller_root_pos'][row][:2],np.float32);rootr=np.asarray(saved['controller_root_rot'][row][:2],np.float32)
 positions=np.asarray(saved['positions'][row][:2],np.float32);rotations=np.asarray(saved['basis'][row][:2],np.float32)
 inv=np.linalg.inv(rootr)
 lp=(positions-rootp[:,None])@inv;lr=rotations@inv[:,None]
 primer=dict(body=np.concatenate((lp,lr[:,:,:2,:].reshape(2,25,6)),-1),root=np.concatenate((rootp,rootr.reshape(2,9)),-1),body_names=tuple(saved['joint_names']))
 slot=next(i for i,r in enumerate(bank.rows) if r['rolloutSha256']==meta['source_npz_sha256'])
 a=bank.frames(slot,yaw_radians=0,target_xz=[0,0],colliders=old['prototype']['collider_catalog'],volume_multiplier=1.5,blade_thickness_multiplier=1.)
 paired=saved['paired_colliders_by_row'][row];axes=np.asarray(paired['attacker_axes'],np.float32);centers=np.asarray(paired['attacker_centers_m'],np.float32)
 rotation=np.swapaxes(a.collider_axes,-1,-2)@axes
 offset=centers-np.einsum('fi,fij->fj',a.collider[:,:3],rotation)
 a.pelvis[:,:3]=np.einsum('fi,fij->fj',a.pelvis[:,:3],rotation)+offset
 a.pelvis[:,3:]=np.einsum('fki,fij->fkj',a.pelvis[:,3:].reshape(-1,2,3),rotation).reshape(-1,6)
 a.positions=np.einsum('fki,fij->fkj',a.positions,rotation)+offset[:,None];a.axes=a.axes@rotation[:,None]
 a.collider=np.concatenate((centers,axes[:,:2].reshape(-1,6)),-1);a.collider_axes=axes;a.target=np.asarray(meta['target_world_m'],np.float32)
 e=episode(primer,a,sk)
 category=entry['lower_category'];agent=load_policy(cp,sk,[category],[meta['attack_name']])
 trace={};counter={'f':1}
 def before(module,inputs):
  counter['f']+=1;tensor_tree(f"frame/{counter['f']:03d}/state_before",inputs[0],trace)
 def after(module,inputs,result):tensor_tree(f"frame/{counter['f']:03d}/proposal",result,trace)
 hs=[agent.register_forward_pre_hook(before),agent.register_forward_hook(after)]
 for name,m in [('upper',agent.upper),('walk',agent.frozen.models['walk']),('run',agent.frozen.models['run']),('frozen_cleaned',agent.frozen)]:
  hs.append(m.register_forward_hook(lambda m,x,y,name=name:(tensor_tree(f"frame/{counter['f']:03d}/{name}/input",x,trace),tensor_tree(f"frame/{counter['f']:03d}/{name}/output",y,trace)) and None))
 with torch.inference_mode():result=rollout(agent,e)
 for h in hs:h.remove()
 tensor_tree('episode',e,trace);tensor_tree('trajectory',result,trace)
 np.savez_compressed(folder/'trace.npz',**trace)
 flat={k:v.reshape(-1).tolist() for k,v in trace.items()}
 flat['limits']=agent.limits.flatten().tolist();flat['category']=[int(category=='run')]
 (folder/'trace.json').write_text(json.dumps(flat))
 (folder/'meta.json').write_text(json.dumps(dict(replay_row=meta,checkpoint_step=cp['step'],replay_step=saved['step'],category=category,geometry_id=gid,frame_count=len(a.times),source='Exact replayer primers/target/collider; matching source attacker pelvis; saved checkpoint'),indent=2))
 torch.save(dict(fixture=fixture,episode=e,attack=a),folder/'fixture.pt')
 error=np.max(np.abs(result.positions.numpy()[0]-np.asarray(saved['positions'][row])))
 print(row,meta['attack_name'],category,'saved checkpoint versus 50-step newer replay maximum position difference m',error,flush=True)

