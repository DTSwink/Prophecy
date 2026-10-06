"""Stage the October 2026 defense checkpoints and their complete runtime settings.

Install only after the matching exact-forearm runtime has been built. Originals
and provenance are retained in the staging folder; no editor assets are saved.
"""
import argparse
import json
import math
import os
import shutil
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from ExportDefenseNetworks import PROJECT, SOURCES, digest, export, ort


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dodge', type=Path)
    parser.add_argument('parry', type=Path)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args()
    torch.set_num_threads(1)
    stage = args.stage.resolve(); stage.mkdir(parents=True, exist_ok=True)
    target = PROJECT/'Content/locomotion/NN/defense'
    paths = dict(dodge=args.dodge.resolve(), parry=args.parry.resolve())
    cp = {k: torch.load(p, map_location='cpu', weights_only=False) for k, p in paths.items()}
    original = torch.load(SOURCES/'dodge_step_198044.pt', map_location='cpu', weights_only=False)
    contracts = ('kind', 'input_dim', 'output_dim', 'bank_contract', 'leg_contract',
                 'bank_names', 'bank_input_contract', 'foot_floor_contract', 'root_contract')
    for key in contracts:
        assert cp['dodge'][key] == original[key], ('unsupported contract', key)
    assert cp['dodge']['forearm_clamp_contract'] == 'attack_hand_projection_both_forearms_exact_rest_length_zero_margin_v1'
    assert cp['parry']['kind'] == 'parry_frozen_walk_run_upper_free_contact_v1'
    assert cp['parry']['config']['exact_forearms'] is True
    assert cp['parry']['config']['forearm_clamp_margin_m'] == 0
    assert cp['parry']['config']['forearm_clamp_contract'] == 'parry_attack_hand_projection_both_forearms_exact_rest_length_v1'
    overrides = list(cp['dodge']['bank_overrides'].values())
    assert overrides and all(v == overrides[0] for v in overrides), 'Per-family bank limits need separate support'
    assert len(overrides) == 17
    limits = [overrides[0][key] for key in cp['dodge']['bank_names']]
    assert all(math.isfinite(v) and v >= 0 for v in limits)
    (stage/'dodge_banks.json').write_text(json.dumps(dict(limits=limits), indent=2)+'\n')
    settings = {}
    for kind, runtime in cp['dodge']['lower_runtime'].items():
        cfg=runtime['config']; policy=runtime['metadata']['policy']; foot=policy['foot_roll_output_projection']
        assert cfg['predict_residual'] and policy.get('output_reference_root', 'current') == 'current'
        assert not policy.get('fake_gravity', {}).get('enabled', False)
        assert foot['pin_mode'] == 'continuous_sigmoid' and foot['enabled']
        near=foot['near_floor_forced_pin']
        settings[kind]=dict(pose_delta_scale=cfg['pose_delta_scale']/30,
            speed_scale=cfg['max_speed_scale']/30, turn_scale=cfg['max_turn_rate_per_sec_scale']/30,
            ground=cfg.get('foot_roll_ground_y',0),side_blend=cfg.get('foot_roll_side_blend_deg',8)*math.pi/180,
            full_height=near['full_height_m'],fade_height=near['fade_height_m'],
            minimum_pin=near['minimum_pin_probability'] if near['enabled'] else 0,
            steps=foot['integration_steps'],legacy_pin=False,height_gate=foot.get('height_pin_gate_enabled',False))
    (stage/'dodge_lower_settings.json').write_text(json.dumps(settings,indent=2)+'\n')
    report = {'checkpoints':{k:dict(file=str(p),sha256=digest(p),step=int(cp[k]['step'])) for k,p in paths.items()},
              'runtime_requires_exact_forearms':True,'dodge_lower_identities':cp['dodge']['lower_identities'],
              'models':{},'installed':False}
    validation=[]
    rng=np.random.default_rng(20261005)
    for kind,branch,prefix,final,width,out in (
        ('dodge','upper','upper.trunk','upper.delta_head',362,112),
        ('dodge','walk','frozen.models.walk.net','frozen.models.walk.net.6',152,43),
        ('dodge','run','frozen.models.run.net','frozen.models.run.net.6',152,43),
        ('parry','upper','upper.trunk','upper.delta_head',258,90)):
        weights=cp[kind]['model']; name=f'prophecy_{kind}_{branch}.onnx'
        assert all(torch.isfinite(v).all() for v in weights.values())
        npz=stage/(kind+'_weights.npz')
        np.savez(npz, **{k:v.numpy() for k,v in weights.items()})
        with np.load(npz) as data: assert export(data,prefix,final,stage/name)==(width,out)
        opt=ort.SessionOptions();opt.intra_op_num_threads=opt.inter_op_num_threads=1
        session=ort.InferenceSession(str(stage/name),sess_options=opt,providers=['CPUExecutionProvider'])
        inputs=[rng.standard_normal((batch,width),dtype=np.float32) for batch in (1,4,17)]
        reference_dir='parry_unreal_reference_770015' if kind=='parry' else 'dodge_unreal_reference/reference'
        suffix='network/input' if kind=='parry' else f'{branch}/input/0'
        with np.load(SOURCES/reference_dir/'trace.npz') as trace:
            inputs += [trace[k].astype(np.float32) for k in trace.files if k.endswith('/'+suffix)]
        errors=[]
        with torch.inference_mode():
            for index,x in enumerate(inputs):
                y=torch.from_numpy(x)
                for i in (0,3):
                    y=F.linear(y,weights[f'{prefix}.{i}.weight'],weights[f'{prefix}.{i}.bias'])
                    y=F.layer_norm(y,(y.shape[-1],),weights[f'{prefix}.{i+1}.weight'],weights[f'{prefix}.{i+1}.bias'],eps=1e-5)
                    y=F.gelu(y,approximate='none')
                expected=F.linear(y,weights[final+'.weight'],weights[final+'.bias']).numpy()
                actual=session.run(None,{'input':x})[0]
                np.testing.assert_allclose(actual,expected,atol=1e-5,rtol=1e-5)
                errors.append(float(np.max(np.abs(actual-expected))))
                if index<2:validation.append(dict(model=name,width=width,out=out,batch=len(x),input=x.reshape(-1).tolist(),expected=expected.reshape(-1).tolist()))
        report['models'][name]=dict(sha256=digest(stage/name),parity_batches=len(inputs),max_abs_error=max(errors))
    # Independent trainer projection references, including collapsed wrist fallback.
    sys.path.insert(0,str(SOURCES.parent))
    from slash2_hand_clamp import HandClamp, clean_upper, rotation6d
    module=HandClamp([0,1,2,3,4,8,9],[0,1,2,3,4,5,5],[6,7],0.)
    cases=[]
    for kind in ('parry','dodge'):
        geometry=json.loads((target/(kind+'_skeleton.json')).read_text())['geometry']
        offsets=np.array(geometry['full/local_offsets'],dtype=np.float32).reshape(25,3)
        indices=[1,2,3,4,5,14,15,16,6,10,7,11,8,12,9,13]
        off=torch.from_numpy(offsets[indices]).unsqueeze(0)
        lengths=torch.tensor(geometry['full/ik_limb_lengths'],dtype=torch.float32).reshape(4,2)[:2,1].unsqueeze(0)
        for i in range(12):
            upper=clean_upper(torch.from_numpy(rng.standard_normal((1,90),dtype=np.float32)))
            lower=torch.from_numpy(rng.standard_normal((1,9),dtype=np.float32))
            lower[:,3:9]=rotation6d(lower[:,3:9])[:,:2,:].reshape(1,6)
            if i==0:
                # Exact arithmetic at the collapsed wrist avoids comparing
                # opposite sides of a 1e-8 singularity due to FK roundoff.
                identity=torch.tensor([1.,0.,0.,0.,1.,0.])
                lower.zero_();lower[:,3:9]=identity
                for offset in (*range(0,60,6),63,69,78,84):upper[:,offset:offset+6]=identity
                elbows,_=module.elbows(upper,lower,off);upper[:,60:63]=elbows[:,0];upper[:,75:78]=elbows[:,1]
            expected=module(upper,lower,off,lengths)
            cases.append(dict(kind=kind,lower=lower.flatten().tolist(),upper=upper.flatten().tolist(),expected=expected.flatten().tolist()))
    (stage/'validation.json').write_text(json.dumps(dict(networks=validation,forearms=cases)))
    for kind in ('dodge','parry'):
        meta={**report['checkpoints'][kind], 'exact_forearms':True, 'models':{k:v for k,v in report['models'].items() if kind in k},'backup_folder':str(stage/'backup')}
        (stage/(kind+'_checkpoint.json')).write_text(json.dumps(meta,indent=2)+'\n')
    files=list(report['models'])+['dodge_banks.json','dodge_lower_settings.json','dodge_checkpoint.json','parry_checkpoint.json']
    if args.install:
        backup=stage/'backup';backup.mkdir(exist_ok=True)
        previous={}
        for name in files:
            dest=target/name
            if dest.exists():
                assert not (backup/name).exists(), 'Use a fresh staging directory for each install'
                shutil.copy2(dest,backup/name);previous[name]=digest(dest)
            else:previous[name]=None
        try:
            for name in files:
                temp=target/(name+'.checkpoint-update');shutil.copy2(stage/name,temp);os.replace(temp,target/name)
            assert all(digest(stage/name)==digest(target/name) for name in files)
        except BaseException:
            for name,old in previous.items():
                if old:shutil.copy2(backup/name,target/name)
                elif (target/name).exists():(target/name).unlink()
            raise
        report.update(installed=True,previous_sha256=previous,installed_files=files)
    (stage/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
