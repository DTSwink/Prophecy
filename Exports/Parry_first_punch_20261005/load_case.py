"""Portable authored punch + vanilla upper-only Parry replay.
python load_case.py --training-dir PATH/ParryAndDodge --run
Recorded lower locomotion is external conditioning, never future defended upper poses.
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
    from frozen_parry_agent import FrozenUpperParry
    meta=json.loads((HERE/'manifest.json').read_text(encoding='utf-8'))
    seed=json.loads((HERE/'parrier_initial_state.json').read_text(encoding='utf-8'))
    recording=np.load(HERE/'attack_recording.npz',allow_pickle=False)
    lower_recording=np.load(HERE/'lower_motion.npz',allow_pickle=False)
    skeleton_seed=torch.load(HERE/'assets/runtime_skeleton_seed.pt',map_location='cpu',weights_only=False)
    prototype=skeleton_seed['prototype'];source=HERE/'assets/source_skeleton.npz'
    if not source.exists():source.write_bytes(prototype['source_bytes'])
    assert source.read_bytes()==prototype['source_bytes']
    case=native.MotionCase(0,prototype['data'],prototype['record'],prototype['manifest'],source,prototype['data'],Path('.'))
    skeleton=native.build_skeleton([case],torch.device(device));geometry=geometry_tensors(skeleton)
    assert geometry.keys()==skeleton_seed['geometry'].keys()
    for key,value in geometry.items():value.copy_(skeleton_seed['geometry'][key].to(device))
    path=HERE/'assets/parry_checkpoint.pt';assert hashlib.sha256(path.read_bytes()).hexdigest()==meta['checkpoint_sha256']
    cp=torch.load(path,map_location='cpu',weights_only=False)
    def t(value):return torch.as_tensor(np.asarray(value),dtype=torch.float32,device=device)
    cache={key:t(lower_recording[key])[None] for key in ('lower','roots','positions','rotations','baseline_upper')}
    agent=FrozenUpperParry(skeleton,cache,defender_drawn=t([seed['defender_drawn']]),exact_forearms=True).to(device)
    agent.load_state_dict(cp['model'],strict=True);agent.eval()
    state=seed['state'];start=seed['primer_attack_frames'][0];count=cache['lower'].shape[1];stop=start+count
    assert np.array_equal(lower_recording['source_frames'],np.arange(start,stop))
    event=torch.ones((1,count,1),device=device);event[:,:2]=0  # Parry activation, not attacker Hit
    episode=Episode(
        lower_primers=t([state['previous_lower'],state['current_lower']])[None],
        upper_primers=t([state['previous_upper'],state['current_upper']])[None],
        root_primers=t([state['previous_root'],state['current_root']])[None],
        pelvis=t(recording['pelvis'][start:stop])[None],collider=t(recording['collider'][start:stop])[None],
        collider_axes=t(recording['collider_axes'][start:stop])[None],attack_half=t(recording['attack_half'])[None],
        event=event,target_world=t(recording['target_world'])[None],
        attack_type=t(seed['attack_controls']+[seed['defense_type']])[None],
        times=t(np.arange(count))[None],valid=torch.ones((1,count),dtype=torch.bool,device=device),authored_roots=None)
    initialized=agent.initial_state(episode.lower_primers,episode.upper_primers,episode.root_primers)
    check={'previous_lower':'previous_lower','previous_upper':'previous_upper','current_lower':'current_lower','current_upper':'current_upper','initial_delta_world':'initial_delta_world','initial_delta_yaw':'initial_delta_yaw'}
    errors={name:float((getattr(initialized,name).flatten()-t(state[key]).flatten()).abs().max()) for name,key in check.items()}
    for which in ('previous','current'):
        roots=torch.cat((getattr(initialized,which+'_root'),getattr(initialized,which+'_axes').flatten(-2)),dim=-1)
        errors[which+'_root']=float((roots.flatten()-t(state[which+'_root'])).abs().max())
    assert max(errors.values())<2.e-5,errors
    return agent,episode,meta,errors

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--training-dir',required=True);parser.add_argument('--run',action='store_true');parser.add_argument('--device',default='cpu');args=parser.parse_args()
    torch.set_num_threads(1)
    agent,episode,meta,errors=load_case(args.training_dir,args.device)
    report={'initialization_max_abs':max(errors.values()),'initialization_errors':errors,'attack_frame_start':meta['parry_primer_attack_frames'][0],'attack_frame_end':meta['last_parry_attack_frame']}
    if args.run:
        from frozen_parry_agent import rollout
        inputs=[];outputs=[]
        def hook(module,x,y):inputs.append(x[0].detach().cpu().numpy().copy());outputs.append(y[0].detach().cpu().numpy().copy())
        h=agent.upper.register_forward_hook(hook)
        with torch.inference_mode():trajectory=rollout(agent,episode)
        h.remove()
        result={key:getattr(trajectory,key).detach().cpu().numpy() for key in ('positions','rotations','roots','lower','upper')}
        result['policy_inputs']=np.concatenate(inputs);result['policy_outputs']=np.concatenate(outputs)
        assert all(np.isfinite(v).all() for v in result.values())
        np.savez_compressed(HERE/'vanilla_parry_smoke.npz',**result)
        report.update(frames=result['positions'].shape[1],finite=True)
    (HERE/'loader_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
