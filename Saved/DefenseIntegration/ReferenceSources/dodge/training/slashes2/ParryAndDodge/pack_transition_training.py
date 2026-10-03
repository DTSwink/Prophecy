"""Lossless training-input pack for all selected motions; no redundant GT body.

All fields consumed by inference/loss/replayer are retained in float32, together
with source NPZ hashes. Unused future GT body poses, frozen policies and browser
banks are deliberately not uploaded. Original datasets are never modified.
"""
import argparse
from dataclasses import fields
import gzip
import json
import time
from pathlib import Path
import numpy as np
import torch
import prepare_transition_corpus as corpus
from transition_rollout import prepare
from transition_geometry import load_harness_geometry
from transition_collision import label_masks
from harness_bindings import load as bindings

SCHEMA='defense_full_motion_training_pack_v1'
HERE=Path(__file__).resolve().parent
PACKS=HERE/'training_packs_v1'


def geometry_tensors(skeleton):
    result={}
    for prefix in ('lower','full'):
        for name,value in getattr(skeleton.runtime,prefix+'_fk_geometry').items():
            result[prefix+'/'+name]=value
    for name in corpus.native.slash2.LOWER_PROJECTION_GEOMETRY_FIELDS:
        result['projection/'+name]=getattr(skeleton.lower_store,name)
    return result


def build(kind):
    index=corpus.read(corpus.CACHE/'index.json')
    if index['schema']!=corpus.features.SCHEMA:raise ValueError('Wrong target cache')
    rows=[r for r in index['rows'] if (r['motion_kind']<16)==(kind=='dodge')]
    if len(rows)!=5000:raise ValueError('Expected all 5000 selected motions')
    preview=corpus.read(corpus.DEFENSE/'neural_preview_manifest.json')
    manifests={r['dataset']:corpus.read(Path(r['dataset'])/'manifest.json') for r in rows}
    maximum=max(r['count']+2 for r in rows)
    def source_key(row):
        record=corpus.read(Path(row['dataset'])/'records'/f"{row['id']:05d}.json")
        return preview['cases'][record['scene']['locomotionIndex']]['source_relative']
    ordered=sorted(enumerate(rows),key=lambda item:source_key(item[1]))
    entries=[None]*len(rows);geometries=[];sources=[];current=None
    packed_episode={};packed_extra={};started=time.monotonic();first=None
    def put(destination,key,value,slot,pad=False):
        if pad and value.shape[1]!=maximum:
            value=torch.cat((value,value[:,-1:].expand(-1,maximum-value.shape[1],*value.shape[2:])),1)
        if key not in destination:destination[key]=torch.empty((len(rows),*value.shape[1:]),dtype=value.dtype)
        destination[key][slot].copy_(value[0])
    for ordinal,(slot,row) in enumerate(ordered):
        case=corpus.make_case(row,manifests,preview)
        if case.source_path!=current:
            skeleton=corpus.native.build_skeleton(case,torch.device('cpu'))
            current=case.source_path
            geometries.append({k:v.clone() for k,v in geometry_tensors(skeleton).items()})
            sources.append(dict(path=str(current),sha256=corpus.digest(current)))
        episode=prepare([case],skeleton,kind,torch.device('cpu'))
        geometry=load_harness_geometry([case],'cpu')
        if first is None:
            first=dict(data=case.data,record=case.record,manifest=case.manifest,
                source_bytes=case.source_path.read_bytes(),source_name=case.source_path.name,
                collider_catalog=json.loads((Path(case.manifest['frozen_inputs'])/'colliders.json').read_text()),
                harness=geometry.harness_identity)
        elif geometry.harness_identity!=first['harness']:raise ValueError('Mixed harness identities')
        for field in fields(episode):
            value=getattr(episode,field.name)
            if value is None:continue
            pad=field.name in ('pelvis','collider','collider_axes','event','times','authored_roots')
            if field.name=='valid':value=torch.arange(maximum)[None]<len(case.data['time'])
            put(packed_episode,field.name,value,slot,pad)
        local,active=bindings([case],maximum,'cpu')
        put(packed_extra,'foot_local',local,slot)
        put(packed_extra,'foot_override',active,slot)
        put(packed_extra,'authored_display',torch.from_numpy(case.data['root'])[None],slot,True)
        entries[slot]=dict(row=row,geometry=len(geometries)-1,record=case.record,
            hit_time=float(case.data['hit_time']),length=len(case.data['time']))
        if (ordinal+1)%100==0:
            print(json.dumps(dict(kind=kind,packed=ordinal+1,of=len(rows),seconds=round(time.monotonic()-started,1))),flush=True)
    raw=[r['motion_kind'] for r in rows]
    for key,value in zip(('present','blocking','harmful'),label_masks(raw,geometry.names,'cpu')):
        packed_extra[key]=value
    if kind=='parry':packed_extra['block_time']=torch.tensor([e['record']['diagnostics']['timing']['contact'] for e in entries])
    data=dict(schema=SCHEMA,feature_schema=corpus.features.SCHEMA,kind=kind,prototype=first,
        rows=entries,episode=packed_episode,extra=packed_extra,sources=sources,
        geometry={k:torch.cat([g[k] for g in geometries]) for k in geometries[0]},
        geometry_ids=torch.tensor([e['geometry'] for e in entries]),maximum=maximum)
    PACKS.mkdir(exist_ok=True)
    output=PACKS/(kind+'.pt');temp=output.with_suffix('.tmp')
    torch.save(data,temp);temp.replace(output)
    compressed=output.with_suffix('.pt.gz')
    with output.open('rb') as src,gzip.open(compressed,'wb',compresslevel=6) as dst:
        import shutil
        shutil.copyfileobj(src,dst)
    report=dict(kind=kind,motions=len(rows),maximum_frames=maximum,geometry_sources=len(sources),
        pack_bytes=output.stat().st_size,transfer_bytes=compressed.stat().st_size,
        sha256=corpus.digest(output),gzip_sha256=corpus.digest(compressed),
        target_contract=corpus.features.TARGET_CONTRACT,source_index_sha256=corpus.digest(corpus.CACHE/'index.json'),
        policy_future_gt_body=False,source_npzs_unchanged=True)
    (PACKS/(kind+'.json')).write_text(json.dumps(report,indent=2))
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--kind',choices=('dodge','parry'),required=True)
    args=parser.parse_args();torch.set_num_threads(1);torch.set_num_interop_threads(1)
    build(args.kind)
