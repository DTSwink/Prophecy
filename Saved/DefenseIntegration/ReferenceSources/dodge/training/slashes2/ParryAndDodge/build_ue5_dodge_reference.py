"""Golden, causal training-policy rollout and numerical UE5 implementation trace.

No simulator, new dodge solver, AE, or future defender poses are introduced.
The fixture is drawn once with the training sampler and uses the native runtime.
"""
import argparse
from dataclasses import fields, is_dataclass
import hashlib
import json
from pathlib import Path
import secrets
import sys
import zipfile
import numpy as np
import torch
from transition_agents import native
from transition_batch import BalancedSampler
from transition_rollout import Episode,rollout
from pack_transition_training import geometry_tensors
from dodge_banked_checkpoint import load_policy,policy_checkpoint
from dodge_banked_batch import lower_categories,validate_training_pack
from dodge_movement_banks import BANK_NAMES,controls,root_window
from dodge_leg_feedback import foot_box_lowest_y

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def plain(value):
    if isinstance(value,torch.Tensor):return value.detach().cpu().tolist()
    if isinstance(value,np.ndarray):return value.tolist()
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,Path):return str(value)
    if isinstance(value,slice):return dict(start=value.start,stop=value.stop,step=value.step)
    if is_dataclass(value):return {f.name:plain(getattr(value,f.name)) for f in fields(value)}
    if isinstance(value,dict):return {str(k):plain(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [plain(x) for x in value]
    if value is None or isinstance(value,(bool,str,int,float)):return value
    return repr(value)

def write_json(path,value):
    Path(path).write_text(json.dumps(plain(value),indent=2,allow_nan=False),encoding='utf-8')

def make_fixture(pack_path,path,selection_path):
    data=torch.load(pack_path,map_location='cpu',weights_only=False)
    validate_training_pack(data)
    if selection_path.exists():
        selection=json.loads(selection_path.read_text());assert selection['pack_sha256']==digest(pack_path)
    else:
        seed=secrets.randbits(32)
        # Banked Dodge maps every old label to regular before this sampler.
        sampler=BalancedSampler([dict(row=dict(type='dodge_regular')) for _ in data['rows']],seed)
        index=int(sampler.sample(1)[0])
        selection=dict(seed=seed,index=index,pack_sha256=digest(pack_path),sampler='BalancedSampler, all rows regular Dodge; one uniform draw; no rejection')
        write_json(selection_path,selection)
    index=selection['index'];entry=data['rows'][index];geom=int(data['geometry_ids'][index])
    fixture=dict(schema='ue5_banked_dodge_fixture_v1',selection=selection,entry=entry,
        category='run' if lower_categories(data,[entry])[0] else 'walk',
        prototype=data['prototype'],geometry={k:v[geom:geom+1].clone() for k,v in data['geometry'].items()},
        episode={k:v[index:index+1].clone() for k,v in data['episode'].items()},
        extra={k:v[index:index+1].clone() for k,v in data['extra'].items()})
    torch.save(fixture,path)
    return fixture

def build_runtime(fixture,folder,device):
    prototype=fixture['prototype'];source=folder/'source_skeleton.npz'
    if not source.exists():source.write_bytes(prototype['source_bytes'])
    assert source.read_bytes()==prototype['source_bytes']
    case=native.MotionCase(0,prototype['data'],prototype['record'],prototype['manifest'],source,prototype['data'],Path('.'))
    skeleton=native.build_skeleton([case],torch.device(device))
    tensors=geometry_tensors(skeleton)
    assert tensors.keys()==fixture['geometry'].keys()
    for key,target in tensors.items():target.copy_(fixture['geometry'][key].to(device))
    episode=Episode(**{**{k:v.to(device) for k,v in fixture['episode'].items()},'authored_roots':None})
    return skeleton,episode

def tensor_tree(prefix,value,out):
    if isinstance(value,torch.Tensor):out[prefix]=value.detach().cpu().numpy().copy()
    elif is_dataclass(value):
        for f in fields(value):tensor_tree(prefix+'/'+f.name,getattr(value,f.name),out)
    elif isinstance(value,dict):
        for key,item in value.items():tensor_tree(prefix+'/'+str(key),item,out)
    elif isinstance(value,(tuple,list)):
        for i,item in enumerate(value):tensor_tree(prefix+'/'+str(i),item,out)

def describe_model(model):
    return [dict(name=name,class_name=type(module).__name__,extra=module.extra_repr()) for name,module in model.named_modules()]

def build(checkpoint,output,selection_path,pack_path,device='cpu',fixture_path=None):
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    output.mkdir(parents=True,exist_ok=False)
    cp=torch.load(checkpoint,map_location='cpu',weights_only=False)
    if fixture_path:
        fixture=torch.load(fixture_path,map_location='cpu',weights_only=False)
        torch.save(fixture,output/'fixture.pt')
    else:fixture=make_fixture(pack_path,output/'fixture.pt',selection_path)
    assert cp['config']['training_pack_sha256']==fixture['selection']['pack_sha256']
    sk,episode=build_runtime(fixture,output,device)
    family=fixture['entry']['record']['scene']['attack']
    agent=load_policy(cp,sk,[fixture['category']],[family],device)
    arrays={};current={'frame':1};last={};handles=[]
    def record(prefix,inputs,result):
        key=f"frame/{current['frame']:03d}/{prefix}"
        tensor_tree(key+'/input',inputs,arrays);tensor_tree(key+'/output',result,arrays)
        last[prefix]=(inputs,result)
    for name,model in [('upper',agent.upper),('walk',agent.frozen.models['walk']),('run',agent.frozen.models['run']),('frozen_cleaned',agent.frozen)]:
        handles.append(model.register_forward_hook(lambda module,inputs,result,name=name:record(name,inputs,result)))
    def before(module,inputs):
        current['frame']+=1;state=inputs[0]
        tensor_tree(f"frame/{current['frame']:03d}/state_before",state,arrays)
        for kind in ('walk','run'):
            cfg=agent.frozen.configs[kind]
            values,future=root_window(state.previous_root,state.previous_axes,state.current_root,state.current_axes,
                state.initial_delta_world,state.initial_delta_yaw,int(cfg.future_window),
                cfg.max_speed_scale_final,cfg.max_turn_rate_scale_final,state.root_yaw_offset)
            tensor_tree(f"frame/{current['frame']:03d}/{kind}/root_window",values,arrays)
            tensor_tree(f"frame/{current['frame']:03d}/{kind}/extrapolated_root_points",future,arrays)
    def after(module,inputs,result):
        prefix=f"frame/{current['frame']:03d}";state=inputs[0]
        tensor_tree(prefix+'/proposal',result,arrays)
        frozen=last['frozen_cleaned'][1][0];raw=last['upper'][1][0][:,90:]
        pelvis=(frozen[:,:3,None].transpose(-1,-2)@state.current_axes).squeeze(1)+state.current_root
        tensor_tree(prefix+'/controls',controls(raw,state.remaining,pelvis[:,1:2]),arrays)
    handles.extend((agent.register_forward_pre_hook(before),agent.register_forward_hook(after)))
    with torch.no_grad():actual=rollout(agent,episode)
    for handle in handles:handle.remove()
    with torch.no_grad():again=rollout(agent,episode)
    for f in fields(actual):
        a,b=getattr(actual,f.name),getattr(again,f.name)
        if a is not None:torch.testing.assert_close(a,b,atol=0,rtol=0)
    # Independent saved-policy reload, no training optimizer or AE loaded.
    policy=policy_checkpoint(agent,cp['bank_overrides']);torch.save(policy,output/'policy.pt')
    reloaded=load_policy(torch.load(output/'policy.pt',map_location='cpu',weights_only=False),sk,[fixture['category']],[family],device)
    with torch.no_grad():check=rollout(reloaded,episode)
    for f in fields(actual):
        a,b=getattr(actual,f.name),getattr(check,f.name)
        if a is not None:torch.testing.assert_close(a,b,atol=0,rtol=0)
    tensor_tree('episode',episode,arrays);tensor_tree('trajectory',actual,arrays)
    for key,value in arrays.items():
        if np.issubdtype(value.dtype,np.floating):assert np.isfinite(value).all(),key
    np.savez_compressed(output/'trace.npz',**arrays)
    write_json(output/'trace.json',arrays)
    np.savez_compressed(output/'weights.npz',**{k:v.detach().cpu().numpy() for k,v in agent.state_dict().items()})
    # Episode.times is the harness frame coordinate, NOT elapsed seconds.
    length=int(episode.valid[0].sum());fps=float(fixture['prototype']['manifest']['fps'])
    assert fps==30.,'Unexpected training tick rate'
    public=dict(schema='ue5_dodge_rollout_v1',checkpoint_step=cp['step'],fps=fps,
        joint_names=sk.body_names,parents=sk.parents,length=length,
        positions=actual.positions[0,:length],basis=actual.rotations[0,:length],roots=actual.roots[0,:length],
        lower=actual.lower[0,:length],upper=actual.upper[0,:length],
        pins=actual.pin_commands[0,:length-2],remaining_banks=actual.movement_banks[0,:length],
        root_shifts_world=actual.root_shifts_world[0,:length],root_yaw_offsets=actual.root_yaw_offsets[0,:length],
        attack_collider=episode.collider[0,:length],attack_collider_axes=episode.collider_axes[0,:length],
        attack_half=episode.attack_half[0],attacker_pelvis=episode.pelvis[0,:length],target_world=episode.target_world[0],
        attack_type=episode.attack_type[0],times=episode.times[0,:length],time_units='frames',
        seconds=episode.times[0,:length]/fps,selection=fixture['selection'],
        units='meters; row-vector world axes; Y up',category=fixture['category'],family=family)
    write_json(output/'rollout.json',public)
    write_json(output/'fixture_inputs.json',dict(episode=episode,selection=fixture['selection'],category=fixture['category'],entry=fixture['entry']))
    write_json(output/'skeleton.json',dict(joint_names=sk.body_names,parents=sk.parents,
        geometry=fixture['geometry'],lower_payload_slices=sk.runtime.lower_clip.ik_payload_slices,
        lower_limb_specs=sk.runtime.lower_clip.ik_limb_specs,core_bones=native.slash2.CORE_BONES,
        arm_specs=native.slash2.ARM_SPECS,collider_catalog=fixture['prototype']['collider_catalog']))
    write_json(output/'networks.json',dict(upper=describe_model(agent.upper),walk=describe_model(agent.frozen.models['walk']),
        run=describe_model(agent.frozen.models['run']),recipe=cp['recipe'],lower_runtime=cp['lower_runtime'],
        bank_names=BANK_NAMES,limits=agent.limits,
        weights={k:dict(shape=list(v.shape),dtype=str(v.dtype)) for k,v in agent.state_dict().items()}))
    source_files={}
    for module in tuple(sys.modules.values()):
        file=getattr(module,'__file__',None)
        if file:
            p=Path(file).resolve()
            if p.suffix=='.py' and p.is_file() and REPO in p.parents:
                relative=p.relative_to(REPO)
                if relative.parts[0] in ('training','fbx_npz_pipeline'):source_files[relative.as_posix()]=digest(p)
    source_files[Path(__file__).resolve().relative_to(REPO).as_posix()]=digest(__file__)
    with zipfile.ZipFile(output/'reference_source.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in sorted(source_files):archive.write(REPO/relative,relative)
    metadata=dict(schema='ue5_dodge_reference_v1',checkpoint=str(checkpoint.resolve()),checkpoint_sha256=digest(checkpoint),
        checkpoint_step=cp['step'],training_run=cp['config']['run_id'],pack_sha256=fixture['selection']['pack_sha256'],
        selection=fixture['selection'],family=family,category=fixture['category'],length=length,
        backend=device,torch_version=torch.__version__,float32=True,tf32=False,no_optimizer_updates=True,
        direct_training_rollout=True,repeat_exact=True,policy_reload_exact=True,
        game_execution_verified=False,source_files=source_files,
        contracts={key:cp.get(key,cp['config'].get(key)) for key in ('kind','bank_contract','leg_contract','foot_floor_contract','root_contract','bank_input_contract')},
        files={p.name:dict(sha256=digest(p),bytes=p.stat().st_size) for p in output.iterdir() if p.is_file()})
    write_json(output/'manifest.json',metadata)
    print(json.dumps({k:metadata[k] for k in ('checkpoint_step','family','category','length','repeat_exact','policy_reload_exact')}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--pack',type=Path,default=HERE/'training_packs_banked_v2/dodge_height4800_spears300.pt')
    p.add_argument('--selection',type=Path,required=True);p.add_argument('--fixture',type=Path)
    p.add_argument('--device',choices=('cpu','cuda'),default='cpu');a=p.parse_args()
    build(a.checkpoint,a.output,a.selection,a.pack,a.device,a.fixture)
