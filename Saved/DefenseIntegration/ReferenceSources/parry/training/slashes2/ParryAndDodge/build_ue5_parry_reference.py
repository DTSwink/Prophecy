"""Read-only CPU Parry reference, cross-checked against the FINAL training replayer.

No optimization, dataset regeneration, remote GPU, or Unreal edits.
"""
import argparse
from dataclasses import fields, is_dataclass
import gc
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile
import numpy as np
import torch
from transition_agents import native, slash
from transition_rollout import Episode
from pack_transition_training import geometry_tensors
from frozen_parry_agent import FrozenUpperParry, rollout, CHECKPOINT_KIND
import transition_features as features
from transition_geometry import load_geometry, defense_obbs
from frozen_parry_forearm_geometry import thin_forearms

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
REPO=ROOT.parents[1]


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def plain(v):
    if isinstance(v,torch.Tensor): return v.detach().cpu().tolist()
    if isinstance(v,np.ndarray): return v.tolist()
    if isinstance(v,np.generic): return v.item()
    if isinstance(v,Path): return str(v)
    if isinstance(v,slice): return dict(start=v.start,stop=v.stop,step=v.step)
    if is_dataclass(v): return {f.name:plain(getattr(v,f.name)) for f in fields(v)}
    if isinstance(v,dict): return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [plain(x) for x in v]
    if v is None or isinstance(v,(str,bool,int,float)): return v
    return repr(v)


def write(path,data):
    path.write_text(json.dumps(plain(data),indent=2,allow_nan=False),encoding='utf-8')


def tree(key,value,arrays):
    if isinstance(value,torch.Tensor): arrays[key]=value.detach().cpu().numpy().copy()
    elif is_dataclass(value):
        for f in fields(value): tree(key+'/'+f.name,getattr(value,f.name),arrays)
    elif isinstance(value,dict):
        for k,v in value.items(): tree(key+'/'+str(k),v,arrays)
    elif isinstance(value,(list,tuple)):
        for i,v in enumerate(value): tree(key+'/'+str(i),v,arrays)


def main(args):
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    cp=torch.load(args.checkpoint,map_location='cpu',weights_only=False)
    cfg=cp['config'];assert cp['kind']==CHECKPOINT_KIND
    assert digest(args.checkpoint)=='f4ee679611e1013d72b5587e95c87798f92be58b0dfe2826ade6944b31107e3e'
    marker=json.loads(args.replayer.read_text())
    saved_file=args.replayer.parent/marker['data_file']
    assert digest(saved_file)==marker['sha256']
    saved=json.loads(gzip.decompress(saved_file.read_bytes()))
    assert saved['step']==cp['step'] and saved['run_id']==cfg['run_id']
    # Pick the first sword-parry witness in the checkpoint's actual saved batch.
    # Not a new random draw, and not a GT or a rollout from a different step.
    row=next((i for i,r in enumerate(saved['rows']) if r['defense_type']==16),0)
    index=int(cp['batch_indices'][row]);meta=saved['rows'][row]
    assert digest(args.pack)==cfg['training_pack_sha256']
    assert digest(args.cache)==cfg['frozen_lower_cache_sha256']
    data=torch.load(args.pack,map_location='cpu',weights_only=False)
    cached=torch.load(args.cache,map_location='cpu',weights_only=False)
    assert cached['source_pack_sha256']==cfg['training_pack_sha256']
    entry=data['rows'][index];slot=cached['indices'].index(index);gid=int(data['geometry_ids'][index])
    assert entry['row']['id']==meta['clip_id']
    fixture=dict(entry=entry,prototype=data['prototype'],
        geometry={k:v[gid:gid+1].clone() for k,v in data['geometry'].items()},
        episode={k:v[index:index+1].clone() for k,v in data['episode'].items()},
        cache={k:v[slot:slot+1].clone() for k,v in cached['tensors'].items()},
        cache_row=cached['rows'][slot],cache_code_identity=cached['code_identity'],
        selection=dict(pack_index=index,saved_batch_row=row,motion_id=meta['clip_id'],
            method='first sword-parry row in exact final saved training batch',
            checkpoint_step=cp['step'],pack_sha256=cfg['training_pack_sha256'],cache_sha256=cfg['frozen_lower_cache_sha256']))
    del data,cached;gc.collect()
    out=args.output;out.mkdir(parents=True,exist_ok=False)
    torch.save(fixture,out/'fixture.pt')
    p=fixture['prototype'];source=out/'source_skeleton.npz';source.write_bytes(p['source_bytes'])
    write(out/'collider_catalog.json',p['collider_catalog'])
    case=native.MotionCase(0,p['data'],p['record'],p['manifest'],source,p['data'],Path('.'))
    sk=native.build_skeleton([case],torch.device('cpu'))
    for k,target in geometry_tensors(sk).items(): target.copy_(fixture['geometry'][k])
    episode=Episode(**fixture['episode'])
    drawn=float(entry['record']['scene']['drawn'] or entry['row']['motion_kind'] in (16,17))
    assert bool(drawn)==meta['has_sword']
    def make_agent():
        a=FrozenUpperParry(sk,fixture['cache'],defender_drawn=torch.tensor([drawn]))
        a.load_state_dict(cp['model'],strict=True);a.eval();return a
    agent=make_agent();arrays={};counter={'frame':1,'held':0}
    original_step=agent.step;patches=[]
    def step(state,e,frame):
        counter.update(frame=frame,held=0)
        tree(f'frame/{frame:03d}/state_before',state,arrays)
        result=original_step(state,e,frame)
        tree(f'frame/{frame:03d}/proposal',result,arrays)
        return result
    agent.step=step
    def wrap(module,name,tag):
        original=getattr(module,name)
        def wrapped(*a,**kw):
            result=original(*a,**kw)
            suffix=tag
            if tag=='held_target':
                suffix+=f'_{counter["held"]}';counter['held']+=1
            key=f'frame/{counter["frame"]:03d}/{suffix}'
            tree(key+'/input',a,arrays);tree(key+'/kwargs',kw,arrays);tree(key+'/output',result,arrays)
            return result
        patches.append((module,name,original));setattr(module,name,wrapped)
    wrap(native,'_held_target','held_target')
    wrap(features,'conditioning','conditioning')
    wrap(slash,'carry_upper_hybrid_deviation','carry')
    wrap(slash,'paired_raw_full_fk_globals','raw_fk')
    wrap(slash,'full_fk_globals','transported_fk')
    handle=agent.upper.register_forward_hook(lambda m,a,r:(tree(f'frame/{counter["frame"]:03d}/network/input',a[0],arrays),tree(f'frame/{counter["frame"]:03d}/network/output',r[0],arrays)) and None)
    try:
        with torch.inference_mode(): result=rollout(agent,episode)
    finally:
        handle.remove();agent.step=original_step
        for mod,name,original in reversed(patches): setattr(mod,name,original)
    with torch.inference_mode(): again=rollout(make_agent(),episode)
    for f in fields(result):
        a,b=getattr(result,f.name),getattr(again,f.name)
        if a is not None: torch.testing.assert_close(a,b,rtol=0,atol=0)
    count=len(saved['positions'][row]);full_count=int(episode.valid[0].sum())
    comparisons={}
    for key,actual in dict(positions=result.positions[0,:count],basis=result.rotations[0,:count],
        controller_root_pos=result.roots[0,:count,:3],controller_root_rot=result.roots[0,:count,3:].reshape(-1,3,3)).items():
        wanted=torch.tensor(saved[key][row],dtype=actual.dtype)
        comparisons[key]=float((actual-wanted).abs().max())
        torch.testing.assert_close(actual,wanted,rtol=0,atol=2e-4)
    geometry=load_geometry(sk.body_names,parry=True,path=out/'collider_catalog.json',device='cpu')
    thin_forearms(geometry)
    with torch.inference_mode(): centers,axes=defense_obbs(result.positions,result.rotations,geometry)
    pair=saved['paired_colliders_by_row'][row]
    ids=[pair['names'].index(n) for n in geometry.names if n in pair['names']]
    gids=[geometry.names.index(pair['names'][i]) for i in ids]
    for key,actual,wanted in [('collider_centers',centers[0,:count,gids],torch.tensor(pair['centers_m'])[:,ids]),
                              ('collider_axes',axes[0,:count,gids],torch.tensor(pair['axes'])[:,ids])]:
        comparisons[key]=float((actual-wanted).abs().max())
        torch.testing.assert_close(actual,wanted,atol=2e-4,rtol=0)
    # Preserve raw training recording unchanged; this is the GPU contact oracle.
    shutil.copyfile(saved_file,out/saved_file.name)
    shutil.copyfile(args.replayer,out/'training_replayer_manifest.json')
    tree('episode',episode,arrays);tree('cache',fixture['cache'],arrays);tree('trajectory',result,arrays)
    tree('colliders/centers',centers,arrays);tree('colliders/axes',axes,arrays)
    for k,v in arrays.items():
        if np.issubdtype(v.dtype,np.floating): assert np.isfinite(v).all(),k
    np.savez_compressed(out/'trace.npz',**arrays);write(out/'trace.json',arrays)
    np.savez_compressed(out/'weights.npz',**{k:v.detach().numpy() for k,v in cp['model'].items()})
    write(out/'weights.json',cp['model'])
    torch.save(dict(kind=CHECKPOINT_KIND,config=cfg,model=cp['model'],step=cp['step']),out/'policy.pt')
    write(out/'rollout.json',dict(schema='ue5_parry_reference_v1',fps=30,units='meters; Y-up; row-vector bases',
        joint_names=sk.body_names,parents=sk.parents,selection=fixture['selection'],saved_row_metadata=meta,
        training_gpu_positions=saved['positions'][row],training_gpu_basis=saved['basis'][row],
        cpu_positions=result.positions[0,:count],cpu_basis=result.rotations[0,:count],roots=result.roots[0,:count],
        times=episode.times[0,:count],seconds=episode.times[0,:count]/30,
        visible_frames=count,original_episode_frames=full_count,attacker_colliders=pair,
        attacker_pelvis=episode.pelvis[0,:count],attack_type=episode.attack_type[0],
        target_world=episode.target_world[0],defender_drawn=drawn))
    write(out/'inputs.json',dict(episode=episode,cache=fixture['cache'],selection=fixture['selection'],
        cache_row=fixture['cache_row'],scene=entry['record']['scene'],defender_drawn=drawn))
    write(out/'skeleton.json',dict(joint_names=sk.body_names,parents=sk.parents,geometry=fixture['geometry'],
        core_bones=slash.CORE_BONES,arm_specs=slash.ARM_SPECS,
        lower_payload_slices=sk.runtime.lower_clip.ik_payload_slices,
        lower_limb_specs=sk.runtime.lower_clip.ik_limb_specs,
        collider_names=geometry.names,collider_half_sizes_m=geometry.half_sizes_m,
        collider_offsets=geometry.center_offsets_local,forearm_override=geometry.forearm_override))
    write(out/'network.json',dict(input_dim=258,output_dim=90,
        modules=[dict(name=n,type=type(m).__name__,settings=m.extra_repr()) for n,m in agent.upper.named_modules()],
        weights={k:list(v.shape) for k,v in cp['model'].items()}))
    write(out/'training_config.json',cfg)
    sources={}
    for module in tuple(sys.modules.values()):
        file=getattr(module,'__file__',None)
        if file:
            path=Path(file).resolve()
            if path.suffix=='.py' and path.is_file() and REPO in path.parents:
                relative=path.relative_to(REPO)
                if relative.parts[0] in ('training','fbx_npz_pipeline'): sources[relative.as_posix()]=digest(path)
    with zipfile.ZipFile(out/'reference_source.zip','w',zipfile.ZIP_DEFLATED) as z:
        for relative in sorted(sources): z.write(REPO/relative,relative)
    manifest=dict(checkpoint=str(args.checkpoint.resolve()),checkpoint_sha256=digest(args.checkpoint),step=cp['step'],
        run_id=cfg['run_id'],selection=fixture['selection'],source_replayer=str(saved_file.resolve()),
        source_replayer_sha256=marker['sha256'],source_recording_exact_copy=True,backend='CPU float32; one thread',
        fresh_training_decoder_rollout=True,repeat_and_model_reload_bit_exact=True,
        gpu_recording_comparison_max_abs=comparisons,comparison_tolerance=2e-4,
        no_training_or_optimizer_updates=True,unreal_execution_verified=False,
        contact_oracle='saved final GPU replayer; CPU CCD not substituted',
        source_files=sources,files={p.name:dict(sha256=digest(p),bytes=p.stat().st_size) for p in out.iterdir() if p.is_file()})
    write(out/'manifest.json',manifest)
    print(json.dumps(dict(step=cp['step'],selection=fixture['selection'],frames=count,comparison=comparisons,folder=str(out))),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--checkpoint',type=Path,default=ROOT/'saved_defense_checkpoints/parry_step_770015.pt')
    p.add_argument('--pack',type=Path,default=HERE/'parry_height_training_v1/assets/parry_height.pt')
    p.add_argument('--cache',type=Path,default=HERE/'parry_height_training_v1/assets/parry_height_lower.pt')
    p.add_argument('--replayer',type=Path,default=ROOT.parent/'runs/20260911_173830_parry_bs256_freehandidle006_3h/replayer/controller_latest.json')
    p.add_argument('--output',type=Path,default=ROOT/'saved_defense_checkpoints/parry_unreal_reference_770015')
    main(p.parse_args())
