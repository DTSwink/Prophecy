"""Load the recorded attacker + TWO defender primers; run the unmodified Dodge trainer.

Usage: python load_case.py --training-dir PATH/ParryAndDodge --run
No Unreal, attack NN, future defender poses, root hooks, or physics required.
"""
from pathlib import Path
import argparse,json,sys,hashlib
import numpy as np
import torch

HERE=Path(__file__).resolve().parent

def load_case(training_dir,device='cpu'):
    sys.path.insert(0,str(Path(training_dir).resolve()))
    from transition_agents import native
    from pack_transition_training import geometry_tensors
    from transition_rollout import Episode
    from dodge_banked_checkpoint import load_policy
    meta=json.loads((HERE/'manifest.json').read_text(encoding='utf-8'))
    seed=json.loads((HERE/'dodger_initial_state.json').read_text(encoding='utf-8'))
    recording=np.load(HERE/'attack_recording.npz',allow_pickle=False)
    skeleton_seed=torch.load(HERE/'assets/runtime_skeleton_seed.pt',map_location='cpu',weights_only=False)
    prototype=skeleton_seed['prototype']
    source=HERE/'assets/source_skeleton.npz'
    if not source.exists():source.write_bytes(prototype['source_bytes'])
    assert source.read_bytes()==prototype['source_bytes']
    case=native.MotionCase(0,prototype['data'],prototype['record'],prototype['manifest'],source,prototype['data'],Path('.'))
    skeleton=native.build_skeleton([case],torch.device(device))
    geometry=geometry_tensors(skeleton)
    assert geometry.keys()==skeleton_seed['geometry'].keys()
    for key,value in geometry.items():value.copy_(skeleton_seed['geometry'][key].to(device))
    checkpoint_path=HERE/'assets/dodge_checkpoint.pt'
    assert hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()==meta['checkpoint_sha256']
    checkpoint=torch.load(checkpoint_path,map_location='cpu',weights_only=False)
    agent=load_policy(checkpoint,skeleton,[seed['category']],['jabR'],device)
    state=seed['state'];start=seed['primer_attack_frames'][0];count=len(recording['source_frames'])-start
    def t(value):return torch.as_tensor(np.asarray(value),dtype=torch.float32,device=device)
    episode=Episode(
        lower_primers=t([state['previous_lower'],state['current_lower']])[None],
        upper_primers=t([state['previous_upper'],state['current_upper']])[None],
        root_primers=t([state['previous_root'],state['current_root']])[None],
        pelvis=t(recording['pelvis'][start:])[None],
        collider=t(recording['collider'][start:])[None],
        collider_axes=t(recording['collider_axes'][start:])[None],
        attack_half=t(recording['attack_half'])[None],
        event=t(recording['event'][start:])[None],
        target_world=t(recording['target_world'])[None],
        attack_type=t(seed['attack_controls']+[0])[None],  # regular Dodge type, not a weapon flag
        times=t(np.arange(count))[None],  # trainer time is in policy-frame units
        valid=torch.ones((1,count),dtype=torch.bool,device=device),
        authored_roots=None)
    # Verify that the stock two-primer initializer recreates all captured history/banks.
    initialized=agent.initial_state(episode.lower_primers,episode.upper_primers,episode.root_primers)
    check={'previous_lower':'previous_lower','previous_upper':'previous_upper','current_lower':'current_lower','current_upper':'current_upper','initial_delta_world':'initial_delta_world','initial_delta_yaw':'initial_delta_yaw','remaining':'remaining','root_shift_world':'root_shift','root_yaw_offset':'yaw_offset'}
    errors={name:float((getattr(initialized,name).flatten()-t(state[key]).flatten()).abs().max()) for name,key in check.items()}
    assert max(errors.values())<2.e-5,errors
    return agent,episode,meta,errors

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--training-dir',required=True);parser.add_argument('--run',action='store_true');parser.add_argument('--device',default='cpu');args=parser.parse_args()
    torch.set_num_threads(1)
    agent,episode,meta,errors=load_case(args.training_dir,args.device)
    report={'initialization_max_abs':max(errors.values()),'initialization_errors':errors,'attack_frame_start':meta['dodge_primer_attack_frames'][0],'attack_frame_end':meta['frame_count']-1}
    if args.run:
        from transition_rollout import rollout
        with torch.inference_mode():trajectory=rollout(agent,episode)
        result={key:getattr(trajectory,key).detach().cpu().numpy() for key in ('positions','rotations','roots','lower','upper','movement_banks','root_shifts_world','root_yaw_offsets')}
        assert all(np.isfinite(v).all() for v in result.values())
        np.savez_compressed(HERE/'vanilla_dodge_smoke.npz',**result)
        report['frames']=result['positions'].shape[1];report['finite']=True
    (HERE/'loader_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
