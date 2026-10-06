"""Rebuild the pinned October 5 full recurrent UE parity fixtures from local Stepper training assets. Run from the Prophecy project root."""
from pathlib import Path
import sys,json,gzip
import numpy as np
import torch
BASE=Path('C:/Users/singerie/Documents/Cursor/stepper');CODE=BASE/'training/slashes2/ParryAndDodge';sys.path.insert(0,str(CODE))
from build_ue5_dodge_reference import build_runtime,tensor_tree
from dodge_banked_inputs import HeightAttackBank,episode
from transition_agents import native,slash
from frozen_parry_agent import FrozenUpperParry,rollout
torch.set_num_threads(1)
OUT=Path.cwd()/'Saved/Diagnostics/CombatParity20261005/parry_witness';OUT.mkdir(parents=True,exist_ok=True)
saved=json.load(gzip.open(BASE/'training/runs/20261004_150736_parry_bs256_exactforearms_targetnoise6cm_8h/replayer/controller_step_01037750.json.gz','rt'))
old=torch.load(CODE/'parry_height_training_v1/assets/parry_height.pt',map_location='cpu',weights_only=False,mmap=True)
bank=HeightAttackBank(BASE/'training/runs/20261003_shared_defense_attacks_step184064')
cp=torch.load(BASE/'training/slashes2/saved_defense_checkpoints/parry_step_1037725.pt',map_location='cpu',weights_only=False)
for row in (0,14,15):
 meta=saved['rows'][row];index=next(i for i,r in enumerate(old['rows']) if r['row']['id']==meta['clip_id']);gid=int(old['geometry_ids'][index]);folder=OUT/str(row);folder.mkdir(exist_ok=True)
 fixture=dict(prototype=old['prototype'],geometry={k:v[gid:gid+1].clone() for k,v in old['geometry'].items()},episode={k:v[index:index+1].clone() for k,v in old['episode'].items()})
 sk,_=build_runtime(fixture,folder,'cpu')
 template=json.load(open('Content/locomotion/NN/defense/parry_skeleton.json'));template['geometry']={k:v.tolist() for k,v in fixture['geometry'].items()};(folder/'skeleton.json').write_text(json.dumps(template))
 rootp=np.asarray(saved['controller_root_pos'][row],np.float32);rootr=np.asarray(saved['controller_root_rot'][row],np.float32);F=len(rootp)
 positions=np.asarray(saved['positions'][row],np.float32);rotations=np.asarray(saved['basis'][row],np.float32);inv=np.linalg.inv(rootr)
 lp=(positions-rootp[:,None])@inv;lr=rotations@inv[:,None];body=np.concatenate((lp,lr[:,:,:2,:].reshape(F,25,6)),-1);roots=np.concatenate((rootp,rootr.reshape(F,9)),-1)
 primer=dict(body=body[:2],root=roots[:2],body_names=tuple(saved['joint_names']))
 slot=next(i for i,r in enumerate(bank.rows) if r['rolloutFile'].replace(chr(92),'/')==old['rows'][index]['record']['source_attack'].replace(chr(92),'/'))
 a=bank.frames(slot,yaw_radians=0,target_xz=[0,0],colliders=old['prototype']['collider_catalog'],volume_multiplier=1.5,blade_thickness_multiplier=1.)
 for k in ('times','source_frames','pelvis','collider','collider_axes','positions','axes'):setattr(a,k,getattr(a,k)[:F])
 paired=saved['paired_colliders_by_row'][row];axes=np.asarray(paired['attacker_axes'],np.float32);centers=np.asarray(paired['attacker_centers_m'],np.float32)
 rotation=np.swapaxes(a.collider_axes,-1,-2)@axes;offset=centers-np.einsum('fi,fij->fj',a.collider[:,:3],rotation)
 a.pelvis[:,:3]=np.einsum('fi,fij->fj',a.pelvis[:,:3],rotation)+offset;a.pelvis[:,3:]=np.einsum('fki,fij->fkj',a.pelvis[:,3:].reshape(-1,2,3),rotation).reshape(-1,6)
 a.positions=np.einsum('fki,fij->fkj',a.positions,rotation)+offset[:,None];a.axes=a.axes@rotation[:,None]
 a.collider=np.concatenate((centers,axes[:,:2].reshape(-1,6)),-1);a.collider_axes=axes;a.target=np.asarray(meta['target_world_m'],np.float32)
 e=episode(primer,a,sk)
 # Parry's event is the activation latch; Dodge's is the attack Hit latch.
 e.event[:,2:]=1
 lower,_=native.body_to_agent_states(dict(body=body),sk,torch.device('cpu'))
 zero=torch.zeros(F,3);identity=torch.eye(3)[None].expand(F,-1,-1);ids=torch.zeros(F,dtype=torch.long)
 localp,localr=slash.lower_fk_globals(sk.runtime,ids,lower,zero,identity)
 base=slash.upper_state_from_globals(sk.runtime.full_clip,localp,localr,zero,identity)
 worldp=localp@torch.from_numpy(rootr)+torch.from_numpy(rootp)[:,None];worldr=localr@torch.from_numpy(rootr)[:,None]
 cache={k:v[None] for k,v in dict(lower=lower,roots=torch.from_numpy(roots),positions=worldp,rotations=worldr,baseline_upper=base).items()}
 agent=FrozenUpperParry(sk,cache,defender_drawn=torch.tensor([float(meta['has_sword'])]),exact_forearms=True);agent.load_state_dict(cp['model'],strict=True);agent.eval()
 trace={};counter={'f':1};original=agent.step
 def step(state,ep,frame):
  counter['f']=frame;tensor_tree(f'frame/{frame:03d}/state_before',state,trace);result=original(state,ep,frame);tensor_tree(f'frame/{frame:03d}/proposal',result,trace);return result
 agent.step=step
 def hook(m,x,y):tensor_tree(f"frame/{counter['f']:03d}/upper/input",x,trace);tensor_tree(f"frame/{counter['f']:03d}/upper/output",y,trace)
 h=agent.upper.register_forward_hook(hook)
 with torch.inference_mode():result=rollout(agent,e)
 h.remove();tensor_tree('episode',e,trace);tensor_tree('cache',cache,trace);tensor_tree('trajectory',result,trace)
 flat={k:v.reshape(-1).tolist() for k,v in trace.items()};flat['drawn']=[float(meta['has_sword'])]
 np.savez_compressed(folder/'trace.npz',**trace);(folder/'trace.json').write_text(json.dumps(flat))
 (folder/'meta.json').write_text(json.dumps(dict(replay_row=meta,checkpoint_step=cp['step'],replay_step=saved['step'],geometry_id=gid,frame_count=F),indent=2));torch.save(dict(fixture=fixture,episode=e,cache=cache,attack=a),folder/'fixture.pt')
 print(row,meta['attack_name'],'checkpoint/replay position difference',float(np.max(np.abs(result.positions.numpy()[0]-positions))),flush=True)

