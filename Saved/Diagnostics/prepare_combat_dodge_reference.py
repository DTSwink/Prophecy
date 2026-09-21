import sys,json,shutil,hashlib
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[2];folder=root/'Saved/Diagnostics/CombatDemo'
base=Path('C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/saved_defense_checkpoints/dodge_unreal_reference/attack_nn')
sys.path.insert(0,str(base.parents[2]/'ParryAndDodge'))
from dodge_banked_inputs import learned_attack_frames
import torch
info=json.loads((base/'attack_generation.json').read_text());z=np.load(base/info['generated']['rolloutFile'])
native=json.loads((folder/'AttackReference/unreal_chain_audit.json').read_text())
out=np.asarray(native['outputs'],dtype=np.float32)
values={k:z[k].copy() for k in z.files};values['rollout_global_joint_pos_m'][2:]=out[:,131:206].reshape(-1,25,3);values['rollout_global_rot'][2:]=out[:,206:431].reshape(-1,25,3,3)
values['armed_latch'][2:]=out[:,431];values['hit_latch'][2:]=out[:,432]
np.savez(folder/'AttackReference/native_attacker.npz',**values)
fixture=torch.load(base/'fixture.pt',map_location='cpu',weights_only=False)
identity=fixture['entry']['record']['attacker_identity']
placement={k:identity[k] for k in ('yaw_radians','target_xz','volume_multiplier','blade_thickness_multiplier')};placement['colliders']=fixture['prototype']['collider_catalog']
native_path=folder/'AttackReference/native_attacker.npz'
attack=learned_attack_frames(dict(info['generated'],_path=native_path,rolloutSha256=hashlib.sha256(native_path.read_bytes()).hexdigest()),**placement)
with np.load(base/'reference/trace.npz') as trace:
 inputs={k:trace[k].astype(np.float32).copy() for k in trace.files if k.startswith('episode/')}
 assert np.array_equal(inputs['episode/event'][0,:,0],(attack.times>=attack.hit_time).astype(np.float32))
 assert inputs['episode/pelvis'].shape[1]==len(attack.times)
 inputs['episode/pelvis'][0]=attack.pelvis
 inputs['episode/collider'][0]=attack.collider
 inputs['episode/collider_axes'][0]=attack.collider_axes
inputs={k:v.reshape(-1).tolist() for k,v in inputs.items()}
inputs['limits']=json.loads((base/'reference/networks.json').read_text())['limits'][0]
dest=root/'Saved/DefenseIntegration/Models/dodge_trace_inputs.json';backup=folder/'original_dodge_trace_inputs.json'
if not backup.exists():shutil.copy2(dest,backup)
(folder/'native_attack_dodge_inputs.json').write_text(json.dumps(inputs))
shutil.copy2(folder/'native_attack_dodge_inputs.json',dest)
expected=json.loads((base/'nn_attacker.json').read_text())
report=dict(placed_native_attacker_max_mm=float(np.linalg.norm(attack.positions-np.asarray(expected['positions']),axis=-1).max()*1000),frames=len(attack.times),source_frames=attack.source_frames.tolist(),same_hit_time=attack.hit_time==fixture['entry']['hit_time'])
(folder/'attack_to_dodge.json').write_text(json.dumps(report,indent=2));print(report)
