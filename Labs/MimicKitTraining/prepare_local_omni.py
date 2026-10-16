"""Prepare the authorized local all-motion experiment; never starts training."""
import copy,hashlib,json
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[2]


def prepare(output=None):
    output=Path(output or ROOT/'Saved/MimicKitLocal/prepared').resolve()
    checkpoint=ROOT/'Saved/MimicKitTransfer/no-armature-3913/checkpoint'
    sources=[ROOT/'Saved/MimicKitUEFN/omni',ROOT/'Saved/MimicKitUEFN/idle/retarget']
    rows=[];motions=[];hashes={};body_names=None
    for folder in sources:
        manifest=json.loads((folder/'manifest.json').read_text())
        if body_names is None:body_names=manifest['body_names']
        assert manifest['body_names']==body_names
        for row in manifest['motions']:
            path=folder/(row['id']+'.pkl')
            assert path.is_file() and row['duration']>0
            assert row['gait'] in (-1,0,1)
            assert abs(sum(v*v for v in row['direction'])-1)<1e-5
            if row['gait']==-1:assert row['direction']==[1.,0.]
            rows.append(copy.deepcopy(row));motions.append(dict(file=path.as_posix(),weight=1.))
            hashes[row['id']]=hashlib.sha256(path.read_bytes()).hexdigest()
    assert len(rows)==27 and len({r['id'] for r in rows})==27
    assert sum(r['gait']==-1 for r in rows)==1
    assert not any(r['id'].endswith(('_Loop_LL','_Loop_RR')) for r in rows)
    output.mkdir(parents=True,exist_ok=True)
    (output/'motions.yaml').write_text(yaml.safe_dump(dict(motions=motions),sort_keys=False))
    (output/'manifest.json').write_text(json.dumps(dict(status='prepared_waiting_for_transfer_verification',
        body_names=body_names,motions=rows),indent=2))
    configs={name:yaml.safe_load((checkpoint/(name+'_config.yaml')).read_text()) for name in ('env','engine','agent')}
    env=configs['env'];engine=configs['engine'];agent=configs['agent']
    assets=ROOT/'Labs/MimicKitUEFN'
    env.update(char_file=(assets/'humanoid_uefn.xml').as_posix(),motion_file=(output/'motions.yaml').as_posix(),
        omni_manifest=(output/'manifest.json').as_posix(),enable_tar_obs=False,tar_obs_steps=[],enable_phase_obs=False)
    engine.update(uefn_asset_directory=assets.as_posix(),uefn_zero_joint_armature=True,
                  uefn_bounded_velocity_motors=True,uefn_jolt_contact_profile=True)
    assert agent['model']['actor_net']==agent['model']['critic_net']=='fc_1024_512_512'
    assert agent['model']['action_std']==.05 and agent['phase_prediction_weight']==.1
    for name,config in configs.items():(output/(name+'_config.yaml')).write_text(yaml.safe_dump(config,sort_keys=False))
    report=dict(training_launched=False,transfer_required=True,initialization='fresh weights, fresh optimizer and zero counters',
        motions=len(rows),mode_counts={str(g):sum(r['gait']==g for r in rows) for g in (-1,0,1)},
        sampling='equal probability per clip',idle_direction=[1.,0.],phase='two circular clock inputs; next-tick Phase E prediction only',
        four_loss_weights=env['absolute_loss_calibration']['weights'],source_motion_sha256=hashes,
        note='Physics trial is not promoted. Final local launcher must use the verified transfer profile.')
    (output/'preparation.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='source_motion_sha256'}),flush=True)
    return report


if __name__=='__main__':prepare()
