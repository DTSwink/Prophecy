"""Tiny collision-only sidecars; no animation duplication or NN feature change.

Parry leg-block rendering transports an authored foot basis in calf space.
Recover that omitted attachment and apply it to the PREDICTED calf at runtime.
This is training collision metadata, not a future pose/predictor input. Export
the same attachment contract with game collision assets; do not claim it is a
single universal fixed bone offset (the harness varies it during the clip).
"""
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import numpy as np
import torch
from transition_geometry import load_geometry,defense_obbs

HERE=Path(__file__).resolve().parent
CACHE=HERE/'harness_collision_bindings_v1'
SCHEMA='parry_calf_local_foot_boxes_v1'


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def paths(dataset,identifier):
    stem=f'{Path(dataset).name}_{int(identifier):05d}'
    return CACHE/(stem+'.npz'),CACHE/(stem+'.json')


def load(cases,maximum,device):
    local=[];active=[]
    for case in cases:
        count=len(case.data['time'])
        value=np.zeros((count,2,2,2,3),dtype=np.float32);mask=np.zeros((count,2),dtype=np.bool_)
        if int(case.data['motion_kind']) in (22,23):
            path,proof_path=paths(case.base_dataset,case.motion_id)
            proof=read(proof_path)
            source=Path(case.base_dataset)/'motions'/f'{case.motion_id:05d}.npz'
            if proof['schema']!=SCHEMA or proof['source_sha256']!=sha(source) or proof['sidecar_sha256']!=sha(path):
                raise ValueError('Harness foot-attachment source changed')
            frozen=Path(case.manifest['frozen_inputs'])
            if proof['html_sha256']!=read(frozen/'proof.json')['files']['index.html']:
                raise ValueError('Foot bindings belong to another harness')
            with np.load(path,allow_pickle=False) as data:
                value=data['foot_local'];mask=data['foot_override']
            if value.shape!=(count,2,2,2,3) or mask.shape!=(count,2):raise ValueError('Wrong attachment shape')
        l=torch.as_tensor(value,device=device);a=torch.as_tensor(mask,device=device)
        local.append(torch.cat((l,l[-1:].expand(maximum-count,*l.shape[1:]))))
        active.append(torch.cat((a,a[-1:].expand(maximum-count,*a.shape[1:]))))
    return torch.stack(local),torch.stack(active)


def build(limit=0):
    import prepare_transition_corpus as corpus
    torch.set_num_threads(1)
    CACHE.mkdir(exist_ok=True)
    selected=[row for row in corpus.source_rows() if row['motion_kind'] in (22,23)]
    pending=[]
    for row in selected:
        path,proof_path=paths(row['dataset'],row['id'])
        if proof_path.exists():
            proof=read(proof_path)
            if proof['source_sha256']!=row['sha256'] or proof['sidecar_sha256']!=sha(path):
                raise ValueError('Existing collision sidecar changed')
        else:pending.append(row)
    if limit:pending=pending[:limit]
    if not pending:return
    manifest=read(Path(pending[0]['dataset'])/'manifest.json');frozen=Path(manifest['frozen_inputs'])
    html_sha=read(frozen/'proof.json')['files']['index.html']
    if sha(frozen/'index.html')!=html_sha:raise ValueError('Frozen harness changed')
    geometry=load_geometry(manifest['bone_names'],parry=True,path=frozen/'colliders.json')
    names=manifest['bone_names'];indices=[geometry.names.index(name) for name in ('foot_l','ball_l','foot_r','ball_r')]
    signs=torch.tensor(list(itertools.product((-1.,1.),repeat=3)))
    process=subprocess.Popen([str(frozen/'.runtime/electron-v44.1.0-win32-x64/electron.exe'),str(HERE/'harness_bindings_worker.mjs')],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',
        env={**os.environ,'ELECTRON_RUN_AS_NODE':'1','PARRY_FROZEN_INPUTS':str(frozen)},
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)|getattr(subprocess,'BELOW_NORMAL_PRIORITY_CLASS',0))
    try:
        for ordinal,row in enumerate(pending):
            dataset=Path(row['dataset']);record=read(dataset/'records'/f"{row['id']:05d}.json")
            source=dataset/'motions'/f"{row['id']:05d}.npz"
            if sha(source)!=row['sha256']:raise ValueError('Dataset source changed')
            with np.load(source,allow_pickle=False) as data:
                body=torch.tensor(data['body']);root=torch.tensor(data['root']);times=data['time'].tolist()
            process.stdin.write(json.dumps(dict(scene=record['scene'],times=times))+'\n');process.stdin.flush()
            result=json.loads(process.stdout.readline())
            if not result['ok'] or result['kind']!=row['motion_kind']:raise ValueError(result)
            frames=result['frames'];local=torch.tensor([frame['local'] for frame in frames]);active=torch.tensor([frame['active'] for frame in frames])
            root_axes=root[:,3:].reshape(-1,3,3)
            p=body[...,:3] @ root_axes+root[:,None,:3]
            first,second=body[...,3:6],body[...,6:9]
            r=torch.stack((first,second,torch.cross(first,second,dim=-1)),-2) @ root_axes[:,None]
            # Verify actual stored pose, not only a native solve compared to itself.
            native_p=torch.tensor([frame['pose'][1:] for frame in frames])
            if (p-native_p).abs().max()>3e-5:raise ValueError('Native solve differs from saved motion')
            c,a=defense_obbs(p,r,geometry,local,active);worst=0.
            for frame,item in enumerate(frames):
                for index,box in zip(indices,item['boxes']):
                    half=torch.tensor(box['half']);expected=torch.tensor(box['center'])+(signs*half) @ torch.tensor(box['axes'])
                    actual=c[frame,index]+(signs*half) @ a[frame,index]
                    error=(expected[:,None]-actual[None]).square().sum(-1).sqrt().amin(-1).amax().item()
                    worst=max(worst,error)
            if worst>1e-5:raise ValueError(('Harness foot collider parity failed',row,worst))
            path,proof_path=paths(dataset,row['id']);tmp=path.with_suffix('.tmp')
            with tmp.open('wb') as stream:np.savez_compressed(stream,foot_local=local.numpy(),foot_override=active.numpy())
            os.replace(tmp,path)
            proof=dict(schema=SCHEMA,source_sha256=row['sha256'],sidecar_sha256=sha(path),html_sha256=html_sha,
                max_corner_error_m=worst,frames=len(frames),bytes=path.stat().st_size)
            temp=proof_path.with_suffix('.tmp');temp.write_text(json.dumps(proof),encoding='utf-8');os.replace(temp,proof_path)
            print(json.dumps(dict(done=ordinal+1,pending=len(pending),id=row['id'],max_corner_error_m=worst)),flush=True)
    finally:
        process.stdin.close()
        try:process.wait(timeout=15)
        except subprocess.TimeoutExpired:process.kill();process.wait()
        if process.returncode:raise RuntimeError(process.stderr.read())


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=0)
    build(parser.parse_args().limit)
