"""CPU-only diagnostic: probe knee authority from an actual failed native pose.

This is an intervention experiment, not a policy evaluation or recovery claim.
Original Jolt rig, limits, contacts and torque caps are retained.
"""
import argparse
import json
import time
import numpy as np
from native_rig import NativeRig, OUT


def knee_angles(q, meta):
    result = []
    for name in ('calf_l', 'calf_r'):
        i = next(i for i, j in enumerate(meta['joints']) if j['body'] == name)
        w, x, y, z = q[7+4*i:11+4*i]
        # Both source knees have only swing-z freedom.
        result.append(np.rad2deg(2*np.arctan2(z, w)))
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--recording', required=True)
    p.add_argument('--output', default='floor-actuation-audit')
    a = p.parse_args()
    recording = np.load(OUT/(a.recording+'.npz'))
    initial = recording['bodies'][-1].copy()
    baseline = recording['actions'][-1].copy()
    meta = json.loads((OUT/'uefn.json').read_text())
    action_names = []
    for j in meta['joints']:
        action_names.extend(j['body']+':'+str(axis) for axis, mode in enumerate(j['modes']) if mode != 2)
    knees = [action_names.index(name+':2') for name in ('calf_l', 'calf_r')]
    results = []; frames = []; start = time.perf_counter()
    for value in (None, 0., 1., 2., 4., -4.):
        commands = baseline.copy()
        if value is not None:
            commands[knees] = value
        trajectory = []; angles = []; foot_forces = []
        with NativeRig(initial, a.output+'-case', requested_action_history=True) as native:
            q, _ = native.coordinates(); initial_angles = knee_angles(q, meta)
            for _ in range(120):
                state = native.step(commands)
                assert np.isfinite(state).all()
                q, _ = native.coordinates()
                trajectory.append(state); angles.append(knee_angles(q, meta))
                foot_forces.append(sum(native.ground_impulses[native.names[n]]*30 for n in ('foot_l', 'foot_r')))
        trajectory = np.array(trajectory); angles = np.array(angles); frames.append(trajectory)
        results.append({'knee_action_override': value, 'initial_knee_angles_deg': initial_angles,
                        'min_knee_angles_deg': angles.min(0).tolist(), 'max_knee_angles_deg': angles.max(0).tolist(),
                        'final_knee_angles_deg': angles[-1].tolist(),
                        'peak_pelvis_m': float(trajectory[:,0,2].max()), 'final_pelvis_m': float(trajectory[-1,0,2]),
                        'peak_foot_support_n': float(max(foot_forces)),
                        'peak_body_angular_rad_s': float(np.linalg.norm(trajectory[:,:,10:13], axis=-1).max())})
    report = {'rig_sha256': meta['rig_sha256'], 'recording': a.recording, 'seconds_per_case': 4,
              'wall_seconds': time.perf_counter()-start, 'cases': results,
              'scope': 'Constant final recorded commands, with bilateral knee overrides. No geometry/limit/controller changes; not learned recovery.'}
    np.savez_compressed(OUT/(a.output+'.npz'), bodies=np.array(frames))
    (OUT/(a.output+'.json')).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
