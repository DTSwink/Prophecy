"""Run an existing actor in the isolated project Jolt DLL, on CPU only.

This fixture diagnoses transfer using actual solved ground impulses for support.
"""
import argparse
import copy
import json
import time
from pathlib import Path
import numpy as np
import torch
from tensordict import TensorDict
from rsl_rl.models import MLPModel
from scipy.spatial.transform import Rotation as R
from native_rig import NativeRig,initial_states,OUT


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--checkpoint',required=True)
    parser.add_argument('--seconds',type=float,default=10);parser.add_argument('--standing-start',action='store_true')
    parser.add_argument('--output',default='native-evaluation');args=parser.parse_args()
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    path=Path(args.checkpoint);saved=torch.load(path,map_location='cpu',weights_only=False)
    contract=saved['infos']['physical_recovery'];states,rig,meta=initial_states(args.standing_start,contract.get('pose_bank','rig-passive.npz'))
    if contract['rig_sha256']!=meta['rig_sha256'] or not contract.get('native_motors') or not contract.get('relative_targets') or contract.get('gyroscopic_forces',True):
        raise ValueError('Native fixture requires the current relative-action, native-motor, no-gyro contract')
    proof=json.loads((OUT/'relative-native-no-gyro-tests.json').read_text())
    if not proof['passed'] or json.loads(json.dumps(contract['controller']))!=proof['controller']:
        raise ValueError('Checkpoint controller differs from the validated native-fixture mapping')
    receipt=json.loads((OUT/'native-rig-tests.json').read_text())
    if not receipt['passed'] or receipt['rig_sha256']!=meta['rig_sha256'] or not receipt.get('ground_impulse_verified'):
        raise ValueError('Native rig has not passed mapping and solved-support tests')
    config=json.loads((path.parent/'config.json').read_text())['ppo']
    options={k:copy.deepcopy(v) for k,v in config['actor'].items() if k in ('hidden_dims','activation','obs_normalization','distribution_cfg')}
    policy=MLPModel(TensorDict({'actor':torch.zeros(1,218)},batch_size=[1]),config['obs_groups'],'actor',54,**options)
    policy.load_state_dict(saved['actor_state_dict']);policy.eval()
    body_frames=[];joint_frames=[];actions=[];gravity_errors=[];heights=[];pose_steps=0;pose_peak=0;connector_peak=0.
    support_frames=[];supported_steps=0;supported_peak=0
    weight=sum(b['jolt_mass_kg'] for b in rig['bodies'])*9.81
    reference=R.from_quat(np.asarray(meta['reference_qpos'])[[4,5,6,3]]).inv().apply([0,0,-1]);start=time.perf_counter()
    with NativeRig(states,args.output,requested_action_history=contract.get('previous_action_observation')=='requested') as native,torch.inference_mode():
        for _ in range(round(args.seconds*30)):
            obs=torch.from_numpy(native.observation()[None,:])
            action=policy(TensorDict({'actor':obs},batch_size=[1])).numpy()[0]
            state=native.step(action);q,v=native.coordinates();body_frames.append(state);joint_frames.append(q);actions.append(action)
            connector_peak=max(connector_peak,float(native.connector_gaps().max()))
            error=float(np.sum((R.from_quat(q[[4,5,6,3]]).inv().apply([0,0,-1])-reference)**2));gravity_errors.append(error);heights.append(q[2])
            pose_steps=pose_steps+1 if error<.1 and q[2]>.9*meta['reference_qpos'][2] and np.linalg.norm(v[:3])<.5 else 0
            pose_peak=max(pose_peak,pose_steps)
            forces=native.ground_impulses*30
            foot_force=sum(forces[native.names[n]] for n in ('foot_l','foot_r'))
            supported=pose_steps>0 and np.linalg.norm(v[3:6])<.5 and foot_force>.5*weight and foot_force>=.9*forces.sum()
            supported_steps=supported_steps+1 if supported else 0;supported_peak=max(supported_peak,supported_steps)
            support_frames.append(forces.copy())
    frames=np.asarray(body_frames)
    np.savez_compressed(OUT/(args.output+'.npz'),bodies=frames,qpos=joint_frames,actions=actions,gravity_error=gravity_errors,
        ground_vertical_force_n=support_frames)
    report={'checkpoint':str(path),'iteration':saved['iter'],'initial':'standing' if args.standing_start else 'fixed',
        'seconds':args.seconds,'wall_seconds':time.perf_counter()-start,'rig_sha256':meta['rig_sha256'],
        'finite':bool(np.isfinite(frames).all()),'max_pose_only_standing_ticks':pose_peak,
        'max_supported_standing_ticks':supported_peak,'supported_standing_for_1s':supported_peak>=30,
        'support_measurement':'Actual solved ground normal impulses accumulated over all 8 physics substeps; feet >50% bodyweight, >=90% ground support; root angular speed <.5rad/s',
        'pelvis_peak_m':float(max(heights)),'pelvis_final_m':float(heights[-1]),'final_gravity_error':gravity_errors[-1],
        'peak_body_angular_rad_s':float(np.linalg.norm(frames[:,:,10:13],axis=2).max()),
        'max_joint_connector_gap_m':connector_peak,
        'engine':'Exact project Jolt Development DLL; isolated process; original limits/collision shapes/effective inertia/caps, .7 friction, zero restitution',
        'motor':'Damped velocity target (torque-saturation integration differs from MuJoCo)',
        'verified_recovery':not args.standing_start and supported_peak>=30,
        'limitation':'Isolated Jolt fixture; no gameplay integration or full dynamics parity claim'}
    (OUT/(args.output+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
