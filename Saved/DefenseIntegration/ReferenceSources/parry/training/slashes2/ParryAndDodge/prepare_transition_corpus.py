"""Incremental, single-worker joint-prior feature cache; source NPZs untouched.

Uses the existing defense native-DOF projection (including semantic toe signs),
not a second skeleton converter. Cache is one append-only float32 file plus an
atomic index; interrupted uncommitted tails are discarded on resume.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
DEFENSE=ROOT/'DefenseHarness'
PARRY=ROOT/'ParryHarness'
for directory in (ROOT,DEFENSE,HERE):sys.path.insert(0,str(directory))
import numpy as np
import torch
import train_imitation_smoke as native
import transition_features as features
from transition_target import recover_world_target
from defense_labels import RAW_TO_TYPE,PARRY_TYPES

DODGE_DATA=DEFENSE/'imitation_5000_noise_lower07_upper001_comroot0_20260905'
PARRY_DATA=PARRY/'imitation_5000_noise_lower07_upper001_authored_20260905'
EXTRA_DATA=PARRY/'imitation_balance_1000_per_type_20260906'
CACHE=HERE/'joint_prior_cache_world_target_v2'
SEED=20260906


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def atomic(path,data):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data,separators=(',',':')),encoding='utf-8')
    os.replace(temporary,path)


def source_rows():
    result=[];parry=defaultdict(list)
    for dataset in (DODGE_DATA,PARRY_DATA,EXTRA_DATA):
        if not (dataset/'records').exists():continue
        for path in sorted((dataset/'records').glob('*.json')):
            record=read(path)
            row=dict(dataset=str(dataset),id=record['id'],type=RAW_TO_TYPE[record['motion_kind']],
                motion_kind=record['motion_kind'],sha256=record.get('sha256') or
                digest(dataset/'motions'/f"{record['id']:05d}.npz"))
            if dataset==PARRY_DATA:parry[row['type']].append(row)
            else:result.append(row)
    for kind,rows in parry.items():
        random.Random(f'{SEED}:{kind}').shuffle(rows)
        result.extend(rows[:1000])
    return result


def row_key(row):return f"{Path(row['dataset']).name}/{row['id']:05d}"


def make_case(row,manifests,preview):
    dataset=Path(row['dataset']);record=read(dataset/'records'/f"{row['id']:05d}.json")
    source_row=preview['cases'][record['scene']['locomotionIndex']]
    if Path(source_row['file']).name!=record['source_defense']:
        raise ValueError('Preview-bank source differs from recorded generation')
    source=ROOT/'walk_run_sword_prep/holding_sword_npz'/source_row['source_relative']
    path=dataset/'motions'/f"{row['id']:05d}.npz"
    if digest(path)!=row['sha256']:raise ValueError('Source motion hash mismatch')
    with np.load(path,allow_pickle=False) as archive:data={key:archive[key] for key in archive.files}
    if not all(np.isfinite(value).all() for value in data.values()):raise ValueError('Nonfinite dataset motion')
    if int(data['motion_kind'])!=row['motion_kind']:raise ValueError('Motion label mismatch')
    # Legacy storage conversion happens once, before slicing/causal inference.
    data['target_world']=recover_world_target(data)
    return native.MotionCase(row['id'],data,record,manifests[str(dataset)],source,data,dataset)


@torch.no_grad()
def encode(case,skeleton):
    data=case.data
    roots=torch.tensor(data['root'])
    positions=roots[:,:3]
    original_axes=roots[:,3:].reshape(-1,3,3)
    axes=original_axes
    projected_data=data
    if int(data['motion_kind'])<16:
        # The new Dodge policy keeps its initial heading. Preserve every world
        # limb while re-expressing the existing zero-tolerance COM-root corpus.
        axes=original_axes[:1].expand_as(original_axes)
        body=torch.tensor(data['body'])
        change=original_axes @ axes.transpose(-1,-2)
        local=body.clone()
        local[...,:3]=body[...,:3] @ change
        local[...,3:]=(body[...,3:].reshape(-1,25,2,3) @ change[:,None]).flatten(-2)
        projected_data={**data,'body':local.numpy()}
    lower,upper=native.body_to_agent_states(projected_data,skeleton,torch.device('cpu'))
    previous=native._held_target(lower[:-2],upper[:-2],skeleton,positions[:-2],axes[:-2],positions[1:-1],axes[1:-1])
    following=native._held_target(lower[2:],upper[2:],skeleton,positions[2:],axes[2:],positions[1:-1],axes[1:-1])
    def world(key):
        value=torch.tensor(data[key])
        point=(value[:,:3,None].transpose(-1,-2) @ original_axes).squeeze(-2)+positions
        rotation=(value[:,3:].reshape(-1,2,3) @ original_axes).flatten(-2)
        return torch.cat((point,rotation),-1)
    pelvis,attack=world('attacker_pelvis'),world('attack')
    delta,yaw=features.initial_root_command(roots[0:1],roots[1:2])
    count=len(roots)-2
    event_threshold=float(data['hit_time']) if int(data['motion_kind'])<16 else 2.0
    event=torch.tensor(data['time'][2:]>=event_threshold,dtype=torch.float32)[:,None]
    conditioning=features.conditioning(pelvis[1:-1],pelvis[2:],attack[1:-1],attack[2:],event,
        delta.expand(count,-1),yaw.expand(count,-1),positions[1:-1],axes[1:-1],
        torch.tensor(data['target_world'])[None].expand(count,-1),
        torch.tensor(data['attack_type'])[None].expand(count,-1))
    result=features.predictor_row(*previous,lower[1:-1],upper[1:-1],*following,conditioning)
    if result.shape!=(count,features.FEATURE_DIM) or not torch.isfinite(result).all():
        raise ValueError('Invalid joint transition row')
    return result.numpy()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=0)
    args=parser.parse_args();torch.set_num_threads(1);torch.set_num_interop_threads(1)
    CACHE.mkdir(exist_ok=True)
    from DefenseHarness.generate_imitation_dataset import single_generator
    with single_generator(CACHE):
        build(args)


def build(args):
    # Changes to the projection, root codec or feature schema require a new
    # cache directory; never silently mix old/new targets in a resumed cache.
    paths=[Path(__file__),HERE/'transition_features.py',HERE/'transition_target.py',DEFENSE/'train_imitation_smoke.py',
           ROOT/'target_frame_codec.py',DEFENSE/'neural_preview_manifest.json']
    code={path.name:digest(path) for path in paths}
    index_path=CACHE/'index.json'
    index=read(index_path) if index_path.exists() else dict(schema=features.SCHEMA,width=features.FEATURE_DIM,code=code,rows=[],frames=0)
    if index['schema']!=features.SCHEMA or index['code']!=code:raise ValueError('Feature cache code identity changed')
    known={row_key(row):row for row in index['rows']}
    selected=source_rows();preview=read(DEFENSE/'neural_preview_manifest.json')
    manifests={path:read(Path(path)/'manifest.json') for path in {row['dataset'] for row in selected}}
    pending=[row for row in selected if row_key(row) not in known]
    for row in selected:
        if row_key(row) in known and known[row_key(row)]['sha256']!=row['sha256']:raise ValueError('Cached motion source changed')
    # Group by immutable source geometry to avoid rebuilding it per variant.
    def source(row):
        record=read(Path(row['dataset'])/'records'/f"{row['id']:05d}.json")
        return preview['cases'][record['scene']['locomotionIndex']]['source_relative']
    pending.sort(key=source)
    if args.limit:pending=pending[:args.limit]
    binary=CACHE/'features.f32';skeleton=None;current_source=None;started=time.monotonic()
    with binary.open('r+b' if binary.exists() else 'w+b') as stream:
        expected=index['frames']*features.FEATURE_DIM*4
        stream.seek(0,2)
        if stream.tell()<expected:raise ValueError('Committed feature file is truncated')
        stream.truncate(expected);stream.seek(expected)
        for ordinal,row in enumerate(pending):
            case=make_case(row,manifests,preview)
            if case.source_path!=current_source:
                skeleton=None
                skeleton=native.build_skeleton(case,torch.device('cpu'));current_source=case.source_path
            values=encode(case,skeleton)
            values.astype(np.float32,copy=False).tofile(stream)
            index['rows'].append({**row,'start':index['frames'],'count':len(values)})
            index['frames']+=len(values)
            if (ordinal+1)%25==0 or ordinal+1==len(pending):
                stream.flush();os.fsync(stream.fileno());atomic(index_path,index)
                print(json.dumps(dict(cached=len(index['rows']),frames=index['frames'],elapsed=time.monotonic()-started)),flush=True)
    print(json.dumps(dict(state='prepared_current_committed_sources',motions=len(index['rows']),frames=index['frames'])),flush=True)


if __name__=='__main__':main()
