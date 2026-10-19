"""Prepare the 50-clip experiment and fixed auto-phase scale; never rent or train."""
import copy, hashlib, json, pickle
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
import yaml

ROOT=Path(__file__).resolve().parents[2]
# Temporary user-requested curriculum; restore to1 when requested.
RUN_MOTION_WEIGHT=3.


def prepare(output=None):
    output=Path(output or ROOT/'Saved/MimicKitEquipment/prepared')
    output.mkdir(parents=True,exist_ok=True)
    source=ROOT/'Saved/MimicKitUEFN/equipment'
    rows=json.loads((source/'dataset.json').read_text())['motions']
    assert len(rows)==54 and len({r['id'] for r in rows})==54
    # User chose regular BR/FL: Strafe variants share their commands but targets differ.
    excluded={f'M_Neutral_Run_Loop_Strafe_{direction}_{equipment}'
              for direction in ('BR','FL') for equipment in ('Unarmed','Drawn')}
    rows=[r for r in rows if r['id'] not in excluded]
    assert len(rows)==50
    reference=ROOT/'Saved/MimicKitLocal/runs/2026-10-16_02-00_transfer_finetune_512'
    configs={n:yaml.safe_load((reference/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')}
    # Recompute the actual four weighted losses from the latest validated Run LR
    # capture. Stored linear velocities are COM velocities, targets are origins.
    capture=ROOT/'Saved/MimicKitTransfer/no-armature-3913/causal_transfer/solver_warm4013.npz'
    physics=json.loads((ROOT/'Labs/MimicKitUEFN/physics.json').read_text())
    names=json.loads((source/'drawn/manifest.json').read_text())['body_names']
    with np.load(capture) as data:
        actual=data['states'];target=data['targets'];tv=data['target_velocities']
    rot=Rotation.from_quat(actual[...,3:7].reshape(-1,4)).as_matrix().reshape(*actual.shape[:-1],3,3)
    tr=Rotation.from_quat(target[...,3:7].reshape(-1,4)).as_matrix().reshape(*target.shape[:-1],3,3)
    offsets=np.array([physics['bodies'][n]['com'] for n in names])
    velocity=actual[...,7:10]-np.cross(actual[...,10:13],np.einsum('...bij,bj->...bi',rot,offsets))
    target=target.copy();target[...,:2]+=actual[...,:1,:2]-target[...,:1,:2]
    raw=np.array([np.mean((actual[...,:3]-target[...,:3])**2),np.mean((velocity-tv[...,:3])**2),
                  np.mean((rot-tr)**2),np.mean((actual[...,10:13]-tv[...,3:])**2)])
    terms=['position_mse','linear_velocity_mse','rotation_mse','angular_velocity_mse']
    weights=configs['env']['absolute_loss_calibration']['weights']
    body_loss=float(raw @ np.array([weights[n] for n in terms]))
    # Modest fixed scale: exceeding both bounds by 0.5 m/s contributes 10%
    # of the measured Run LR four-term tracking loss. Do not amplify a tiny
    # observed band violation into a large coefficient.
    com_weight = .10 * body_loss / .5**2
    # Opposite unit-circle vectors have component-mean squared error 2.
    phase_weight=body_loss*.15/.85/2
    assert np.isfinite(phase_weight) and phase_weight>0
    calibration=dict(checkpoint=str(reference/'model.pt'),checkpoint_sha256=hashlib.sha256((reference/'model.pt').read_bytes()).hexdigest(),
        capture=str(capture),capture_sha256=hashlib.sha256(capture.read_bytes()).hexdigest(),samples=int(np.prod(actual.shape[:2])),
        body_loss=body_loss,body_terms=dict(zip(terms,(raw*np.array([weights[n] for n in terms])).tolist())),
        maximum_auto_phase_mse=2.,auto_phase_weight=phase_weight,fraction_of_combined_at_maximum=.15,
        interpretation='Fixed supervised actor auxiliary weight, calibrated against physical tracking loss; not a guarantee of gradient contribution')
    configs['agent'].pop('phase_prediction_weight',None)
    configs['agent'].update(auto_phase_weight=phase_weight,iters_per_output=100,iters_per_log=10,test_episodes=32)
    configs['agent']['model']['auto_phase_unit_output']=True
    configs['agent']['model'].update(actor_net='fc_1024_1024_512',critic_net='fc_1024_1024_512')
    configs['env'].update(equipment_conditioning=True,arm_injuries_enabled=False,idle_row_fraction=.06,
        adaptive_motion_rows=dict(interval_seconds=60.,max_failure_weight=3.),
        flat_com_velocity_loss=dict(weight=com_weight,leeway=.10,
            calibration=dict(reference_body_loss=body_loss,axis_excess_m_s=.5,fraction_of_body_loss=.10)),
        char_file=(ROOT/'Labs/MimicKitUEFN/humanoid_uefn.xml').as_posix(),
        motion_file=(output/'motions.yaml').resolve().as_posix(),omni_manifest=(output/'manifest.json').resolve().as_posix(),
        enable_tar_obs=False,tar_obs_steps=[],enable_phase_obs=False)
    configs['engine'].update(uefn_asset_directory=(ROOT/'Labs/MimicKitUEFN').as_posix(),
        uefn_zero_joint_armature=True,uefn_bounded_velocity_motors=True,uefn_jolt_contact_profile=True)
    for row in rows:
        frames=pickle.loads(Path(row['file']).read_bytes())['frames']
        assert np.isfinite(frames).all() and frames.shape[1]==40
    (output/'motions.yaml').write_text(yaml.safe_dump(dict(motions=[dict(file=r['file'],weight=RUN_MOTION_WEIGHT if r['gait']==1 else 1.) for r in rows])))
    (output/'manifest.json').write_text(json.dumps(dict(body_names=names,motions=rows),indent=2))
    for n,c in configs.items():(output/(n+'_config.yaml')).write_text(yaml.safe_dump(c,sort_keys=False))
    (output/'auto-phase-calibration.json').write_text(json.dumps(calibration,indent=2))
    print(json.dumps(calibration,indent=2))
    return output


if __name__=='__main__':prepare()
