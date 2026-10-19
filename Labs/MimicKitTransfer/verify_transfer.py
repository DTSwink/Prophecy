"""Explicit acceptance receipt for the measured flat-floor transfer domain."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitTransfer/no-armature-3913'


def require_matching_body(native_assets,mj_assets):
    # These fixed native reports used the archived body, not today's PHAT export.
    # Hashing today's export after reading old reports cannot certify that export.
    paths=[];changed=[]
    for name in ('humanoid_uefn.xml','limits.json','physics.json'):
        native_path=native_assets/name;mj_path=mj_assets/name
        if native_path.read_bytes()!=mj_path.read_bytes():changed.append(name)
        paths.append(native_path)
    if changed:
        raise RuntimeError('Native transfer evidence uses a different body: '+', '.join(changed)+
            '. Revalidate the updated body in native Jolt before issuing a transfer receipt.')
    return paths


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mj-label',default='local_finetune4013_phases16',help='Fresh MJ regression; native rig/checkpoint remain unchanged')
    args=parser.parse_args()
    native_body_paths=require_matching_body(OUT/'source/assets/uefn',ROOT/'Labs/MimicKitUEFN')
    folder=OUT/'causal_transfer';stem='local_finetune4013_phases16'
    mj_path=folder/(args.mj_label+'.json')
    mj=json.loads(mj_path.read_text())
    native=json.loads((folder/(stem+'_self0_native_v40p8_point.json')).read_text())
    checkpoint=ROOT/'Saved/MimicKitLocal/runs/2026-10-16_02-00_transfer_finetune_512'
    assert Path(mj['checkpoint']).resolve()==(checkpoint/'model.pt').resolve()
    assert mj['worlds']==len(native)==16 and mj['ticks']==300
    assert mj['first_flags']==[3]*16 and mj['first_done']==[300]*16
    assert max(mj['max_distance'])<.27
    assert all(r['ticks']==300 and not r['target_failure'] and r['max_target_distance_m']<.27 for r in native)
    assert all(r['initial_state']=='animation reset before physics' and not r['no_limits_diagnostic'] for r in native)
    assert all(r['rig_iterations']==[40,8] and r['native_self_friction']==0 for r in native)
    assert all(r['solved_ground_impulse_ns']>7000 and r['foot_ground_impulse_fraction']>.999 for r in native)
    assert max(r['observation_mapping_max_error'] for r in native)<1e-3
    long_path=folder/'long_run4013_native40_floor1000.json'
    remaining_path=folder/'long_run4013_native40_floor1000_remaining.json'
    long=json.loads(long_path.read_text())+json.loads(remaining_path.read_text())
    assert sorted(r['start_phase'] for r in long)==[i/16 for i in range(16)]
    assert len(long)==16 and all(r['ticks']==1800 and r['resets']==0 and not r['target_failure']
        and r['max_target_m']<.27 and r['foot_ground_fraction']>.999 for r in long)
    inputs=[mj_path,folder/(stem+'_self0_native_v40p8_point.json'),checkpoint/'model.pt',
            OUT/'point-contact/profile/fixture.exe',OUT/'point-contact/profile/ProphecyJolt_5_6_Development.dll']
    inputs += [ROOT/'Labs/MimicKitTransfer'/name for name in ('contact_engine.py','sequential_contact_adapter.py',
        'sequential_contact_gpu.py','block_contact_gpu.py','contact_manifolds_gpu.py','jolt_limit_directions.py','limit_projection_gpu.py')]
    inputs += [ROOT/'Labs/MimicKitUEFN'/name for name in ('humanoid_uefn.xml','limits.json','physics.json',
        'runtime.py','velocity_motors.py','body_velocity.py')]
    inputs.append(ROOT/'Labs/MimicKitTraining/uefn_engine.py')
    inputs.extend([long_path,remaining_path,OUT/'point-contact/profile/long-floor/fixture.exe',
                   OUT/'point-contact/profile/long-floor/build.json'])
    inputs.extend(native_body_paths)
    report=dict(accepted=True,domain='Run LR, flat ground, 16 evenly spaced true animation starts, 10 seconds each',
        mj_report=str(mj_path.relative_to(ROOT)),
        native_starts=16,native_successes=16,ticks=300,mj_successes=16,
        uninterrupted_native_starts=16,uninterrupted_seconds=60,
        uninterrupted_max_target_m=max(r['max_target_m'] for r in long),
        checkpoint=str(checkpoint/'model.pt'),native_iterations=[40,8],
        max_native_target_m=max(r['max_target_distance_m'] for r in native),max_mj_target_m=max(mj['max_distance']),
        mean_native_policy_tick_ms=float(np.mean([r['physics_update_ms_mean'] for r in native])),
        contact_profile='tagged rig only: per-point speculative contacts off; self friction0; ground friction1/rest0',
        limits='original exported PHAT limits, no disabled limits',
        limitation='Behavioral transfer within original27cm termination bound; native16x60s also pass. Not bit-identical trajectories, untested terrain/disturbances or live Unreal integration.',
        installed_gameplay_jolt_unchanged=True,sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs})
    path=OUT/'verified_transfer.json';path.write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)


if __name__=='__main__':main()
