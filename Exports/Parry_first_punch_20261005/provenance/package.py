from pathlib import Path
import sys,json,shutil,hashlib,subprocess
import numpy as np
from scipy.spatial.transform import Rotation
import torch
ROOT=Path.cwd();P=ROOT/'Exports/Parry_first_punch_20261005';RAW=P/'reference_unreal'
BASE=Path('C:/Users/singerie/Documents/Cursor/stepper');CODE=BASE/'training/slashes2/ParryAndDodge';sys.path.insert(0,str(CODE))
torch.set_num_threads(1)
def write(path,data):path.write_text(json.dumps(data,indent=2,allow_nan=False),encoding='utf-8')
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
d=read(RAW/'capture.json');assert d['reason']=='complete',d['reason']
family=d['first_punch_family'];starttick=d['first_punch_start']
selected=[r for r in d['rows'] if r['tick']>=starttick and r['attack'] and r['attack']['family']==family]
byframe={}
for r in selected:byframe.setdefault(r['attack']['frame'],r)
frames=sorted(byframe);assert frames==list(range(1,max(frames)+1)),frames
initial_paths=[p for p in sorted(RAW.glob('*_initial.json')) if int(p.name[:4])>=starttick and read(p)['family'].lower()==family.lower()]
assert len(initial_paths)==1,initial_paths
first=read(initial_paths[0]);initial=first['state'];assert initial['steps']==0
activation=first['frame'];primer_start=activation-2
upper=[p for p in sorted(RAW.glob('*_before.json')) if int(p.name[:4])>=starttick and read(p)['family'].lower()==family.lower() and read(p)['owner']==first['owner']]
before=[read(f) for f in upper];assert [f['frame'] for f in before]==list(range(activation,activation+len(before)))
assert before[0]['state']['steps']==0
names=read(ROOT/'Content/locomotion/NN/defense/parry_skeleton.json')['joint_names']
ordered=[byframe[f] for f in frames];allposes=[ordered[0]['attacker']['previous']]+[r['attacker']['future'] for r in ordered]
source_names=ordered[0]['attacker']['names'];idx=[source_names.index(n) for n in names]
position_ue=np.array([[t['p_cm'] for t in pose] for pose in allposes])[:,idx];quat_ue=np.array([[t['q_xyzw'] for t in pose] for pose in allposes])[:,idx]
origin=np.zeros(3,dtype=np.float32)
positions=(position_ue[:,:,[0,2,1]]*.01).astype(np.float32)
swap=np.eye(3)[[0,2,1]];sign=np.diag([1,-1,1])
rotations=(sign@Rotation.from_quat(quat_ue.reshape(-1,4)).as_matrix().transpose(0,2,1)@swap).reshape(len(allposes),25,3,3).astype(np.float32)
catalog=read(ROOT/'Content/locomotion/NN/defense/attacker_colliders.json');bone='lowerarm_l' if family.lower().endswith('l') else 'lowerarm_r'
box=next(x for x in catalog['colliders'] if x['name']==bone);bi=names.index(bone);assert bi==box['bone']
centers=positions[:,bi]+np.asarray(box['offset'],np.float32)@rotations[:,bi];box_axes=np.array(box['axes'],np.float32).reshape(3,3)@rotations[:,bi];box_axes/=np.linalg.norm(box_axes,axis=-1,keepdims=True)
collider=np.concatenate((centers,box_axes[:,:2].reshape(-1,6)),axis=-1);pelvis=np.concatenate((positions[:,0],rotations[:,0,:2].reshape(-1,6)),axis=-1)
targets=np.array([r['target']['requested_cm'] for r in ordered],np.float32)[:,[0,2,1]]*.01
assert np.max(np.abs(targets-targets[0]))<1.e-6
assert np.max(np.abs(targets[0]-np.array(first['target'])))<1.e-6
checks=[]
for u in before:
 frame=u['frame'];checks.append({'frame':frame,'pelvis_max_abs':float(np.max(np.abs(pelvis[frame-1:frame+1].reshape(-1)-u['pelvis']))),'collider_max_abs':float(np.max(np.abs(collider[frame-1:frame+1].reshape(-1)-u['collider'])))})
write(P/'input_validation.json',checks);assert max(max(x['pelvis_max_abs'],x['collider_max_abs']) for x in checks)<2.e-5,checks
armed=np.array([False]+[r['attack']['armed'] for r in ordered]);hit_latch=np.array([False]+[r['attack']['hit'] for r in ordered],np.float32)[:,None]
hits=np.flatnonzero(hit_latch[:,0]);hit=int(hits[0]) if len(hits) else None
np.savez_compressed(P/'attack_recording.npz',source_frames=np.arange(len(allposes)),times_seconds=np.arange(len(allposes))/30.,game_ticks=np.array([ordered[0]['tick']-1]+[r['tick'] for r in ordered]),joint_names=np.array(names),positions=positions,rotations=rotations,pelvis=pelvis,collider=collider,collider_axes=box_axes,attack_half=np.array(box['half'],np.float32),target_world=targets[0],hit=hit_latch,armed=armed,world_origin=origin,ue_positions_cm=position_ue,ue_quaternions_xyzw=quat_ue)
write(P/'parrier_initial_state.json',dict(attack_family=family,activation_attack_frame=activation,primer_attack_frames=[primer_start,primer_start+1],world_origin_training_m=origin.tolist(),attack_controls=first['attack_controls'],defense_type=0,defender_drawn=before[0]['input'][-1],state=initial))
attackstart=next(r for r in d['rows'] if r['tick']==ordered[0]['tick']-1)
write(P/'parrier_at_attack_start.json',{'tick':attackstart['tick'],'pose':attackstart['defender'],'note':'Display/history at attack start; use Armed-time encoded primers for vanilla Parry.'})
assets=P/'assets';assets.mkdir(exist_ok=True)
for name in ['parry_skeleton.json','parry_colliders.json','attacker_colliders.json','parry_checkpoint.json']:shutil.copy2(ROOT/'Content/locomotion/NN/defense'/name,assets/name)
cp=read(assets/'parry_checkpoint.json');checkpoint=Path(cp['file']);assert hashlib.sha256(checkpoint.read_bytes()).hexdigest()==cp['sha256'];shutil.copy2(checkpoint,assets/'parry_checkpoint.pt')
fixture=torch.load(ROOT/'Saved/Diagnostics/CombatParity20261005/parry_witness/0/fixture.pt',map_location='cpu',weights_only=False)['fixture']
geometry={k:torch.tensor(v,dtype=torch.float32) for k,v in read(assets/'parry_skeleton.json')['geometry'].items()}
torch.save({'prototype':fixture['prototype'],'geometry':geometry},assets/'runtime_skeleton_seed.pt')
from transition_agents import native,slash
from pack_transition_training import geometry_tensors
prototype=fixture['prototype'];source=assets/'source_skeleton.npz';source.write_bytes(prototype['source_bytes'])
case=native.MotionCase(0,prototype['data'],prototype['record'],prototype['manifest'],source,prototype['data'],Path('.'));skeleton=native.build_skeleton([case],torch.device('cpu'))
for k,v in geometry_tensors(skeleton).items():v.copy_(geometry[k])
lower=np.array([initial['previous_lower'],initial['current_lower']]+[v['next_lower'] for v in before],np.float32)
roots=np.array([initial['previous_root'],initial['current_root']]+[v['next_root'] for v in before],np.float32)
T=len(lower);ids=torch.zeros(T,dtype=torch.long);l=torch.from_numpy(lower);r=torch.from_numpy(roots);zero=torch.zeros(T,3);identity=torch.eye(3)[None].expand(T,-1,-1)
localp,localr=slash.lower_fk_globals(skeleton.runtime,ids,l,zero,identity)
base=slash.upper_state_from_globals(skeleton.runtime.full_clip,localp,localr,zero,identity).numpy();base[1]=initial['current_baseline'];base[2:]=np.array([v['next_baseline'] for v in before])
wp=(localp@r[:,3:].reshape(-1,3,3)+r[:,:3,None].transpose(1,2)).numpy();wr=(localr@r[:,None,3:].reshape(T,1,3,3)).numpy()
wp[2:]=np.array([v['frozen_positions'] for v in before]).reshape(-1,25,3);wr[2:]=np.array([v['frozen_rotations'] for v in before]).reshape(-1,25,3,3)
np.savez_compressed(P/'lower_motion.npz',source_frames=np.arange(primer_start,primer_start+T),lower=lower,roots=roots,baseline_upper=base,positions=wp,rotations=wr)
# Native input/output reference is never consumed by the vanilla loader.
np.savez_compressed(RAW/'native_parry_arrays.npz',source_frames=np.array([v['frame'] for v in before]),inputs=np.array([v['input'] for v in before],np.float32),outputs=np.array([read(Path(str(f).replace('_before.json','_after.json')))['output'] for f in upper],np.float32))
manifest=dict(schema='prophecy_authored_attack_parry_seed_v1',attack=family,policy_hz=30,first_attack_game_tick=ordered[0]['tick'],last_attack_game_tick=selected[-1]['tick'],attack_end_game_tick=d['rows'][-1]['tick'],armed_attack_frame=activation,hit_attack_frame=hit,first_parry_game_tick=int(initial_paths[0].name[:4]),parry_primer_attack_frames=[primer_start,primer_start+1],last_parry_attack_frame=before[-1]['frame'],frame_count=len(allposes),target_training_m=targets[0].tolist(),target_ue_cm=ordered[0]['target']['requested_cm'],world_origin_training_m=origin.tolist(),checkpoint_sha256=cp['sha256'],checkpoint_step=cp['step'],post_hit_frames=ordered[0]['defense_delay'],attacker=first['attacker'],defender=first['owner'],defender_drawn=before[0]['input'][-1],coordinate_convention='Metres, Y up, row bases. UE [x,y,z]cm -> [x,z,y]/100. Rotation rows: UE +X,-Y,+Z directions with world Y/Z swapped. No episode origin shift for Parry.',attacker_source='Recorded completed authored UE poses; no attack NN required.',defender_source='Two initial encoded upper primers. The recorded lower-only cache is the immutable locomotion input required by FrozenUpperParry, never a future upper proposal. Vanilla root command remains initialized from primers; UE later planned-root overrides are diagnostic only.',contact_rule='No automatic contact stopping; attacker Hit is a learned latch, not a geometric collision.',native_input_comparison=checks,source_git_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip())
manifest['trainer_source_sha256']={n:hashlib.sha256((CODE/n).read_bytes()).hexdigest() for n in ['frozen_parry_agent.py','frozen_parry_hand_clamp.py','transition_agents.py','transition_features.py']}
write(P/'manifest.json',manifest)
print(json.dumps({k:manifest[k] for k in ['attack','first_attack_game_tick','armed_attack_frame','hit_attack_frame','frame_count','last_parry_attack_frame','defender_drawn']},indent=2))
