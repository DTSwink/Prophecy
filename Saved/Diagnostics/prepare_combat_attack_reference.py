"""Only writes temporary audit fixtures. Original reference/training assets stay untouched."""
import sys,json
from pathlib import Path
from dataclasses import replace
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'Tools/NN'))
from ExportProphecySlashPolicy import slash,torch,np,SlashStep
torch.set_num_threads(2)
base=Path('C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/saved_defense_checkpoints/dodge_unreal_reference/attack_nn')
info=json.loads((base/'attack_generation.json').read_text())
z=np.load(base/info['generated']['rolloutFile'])
_,recipe,lower,upper=slash.load_slash2_rollout_session(Path(info['checkpoint']['path']),torch.device('cpu'))
rt=slash.load_runtime(replace(recipe,predictive_pin_checkpoint=None),torch.device('cpu'),attack_paths=[Path(info['source']['runtimeSourcePath'])],inference_only=True)
model=SlashStep(rt,lower,upper,1).eval()
folder=root/'Saved/Diagnostics/CombatDemo/AttackReference';folder.mkdir(parents=True,exist_ok=True)
native=json.loads((root/'Content/locomotion/NN/prophecy_slash_native.json').read_text())
native.update(root_position=model.root_pos[0].tolist(),root_rotation=model.root_rot[0].tolist(),ground=rt.lower_store.foot_roll_ground_y_tensor.tolist(),lower_geometry={k:v[0].tolist() for k,v in rt.lower_fk_geometry.items()},full_geometry={k:v[0].tolist() for k,v in rt.full_fk_geometry.items()})
(folder/'source_native_geometry.json').write_text(json.dumps(native))
with rt.policy_context(),torch.inference_mode():
 data=rt.attacks;ids=torch.zeros(2,dtype=torch.long);frames=torch.arange(2);target=data.targets_world[:1].expand(2,-1)
 lr=slash.lower_hybrid_state_to_root(rt.lower_store,ids,frames,data.trajectory_lower[0,:2],target,data.trajectory_heading[0,:2])
 ur=slash.upper_hybrid_state_to_root(rt.lower_store,ids,frames,torch.stack((data.initial_previous_upper[0],data.initial_current_upper[0])),target,data.trajectory_heading[0,:2])
 state=torch.cat((lr[0],lr[1],ur[0],ur[1],target[0],data.labels[0],torch.zeros(2)))[None]
 inputs=[];outputs=[]
 for i in range(2,len(z['armed_latch'])):
  inputs.append(state[0].tolist());out=model(state);outputs.append(out[0].tolist())
  state=torch.cat((state[:,41:82],out[:,:41],state[:,172:262],out[:,41:131],state[:,262:270],out[:,431:433]),-1)
a=np.asarray(outputs)
errors=np.linalg.norm(a[:,131:206].reshape(-1,25,3)-z['rollout_global_joint_pos_m'][2:],axis=-1)
summary=dict(python_vs_supplied_max_mm=float(errors.max()*1000),latches_match=bool(np.array_equal(a[:,431],z['armed_latch'][2:]) and np.array_equal(a[:,432],z['hit_latch'][2:])))
assert summary['python_vs_supplied_max_mm']<.1 and summary['latches_match'],summary
# Keep source positions/rotations/latches as independent oracle. State channels only support diagnostics.
expected=a.copy();expected[:,131:206]=z['rollout_global_joint_pos_m'][2:].reshape(-1,75);expected[:,206:431]=z['rollout_global_rot'][2:].reshape(-1,225);expected[:,431]=z['armed_latch'][2:];expected[:,432]=z['hit_latch'][2:]
(folder/'chain_audit.json').write_text(json.dumps(dict(inputs=inputs,expected=expected.tolist(),four_step_oracle=expected.tolist(),segments=[dict(startFrame=2)],note='Legacy oracle field name; exact source 60/4 pinning, regenerated headbutt reference.')))
(folder/'preparation.json').write_text(json.dumps(summary,indent=2));print(summary)
