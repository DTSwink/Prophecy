"""Summarize recorded CPU/GPU evidence without running another simulation."""
import hashlib, io, json, tarfile, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Saved/MimicKitUEFN/dependencies'))
import numpy as np
import mujoco
from scipy.spatial.transform import Rotation as R

OUT = ROOT / 'Saved/MimicKitTransfer/vanilla-calibration'


def main():
    gpu = json.loads((OUT / 'gpu-results.json').read_text())
    meta = json.loads((OUT / 'gpu-packet/packet.json').read_text())
    receipt = json.loads((OUT / 'replacement-session.json').read_text())
    summary = {}
    with tarfile.open(OUT / 'gpu-evidence.tar.gz') as archive:
        for name, result in gpu['evaluations'].items():
            state = np.load(io.BytesIO(archive.extractfile(name + '_gpu.npz').read()))['states']
            m = mujoco.MjModel.from_binary_path(str(OUT / 'gpu-packet' / (name + '.mjb')))
            lowest = np.full(state.shape[:2], np.inf)
            for g in range(m.ngeom):
                b = m.geom_bodyid[g]
                if b == 0:
                    continue
                label = m.body(b).name
                i = next(i for i, n in enumerate(meta['names']) if label.endswith(n))
                rot = R.from_quat(state[:, :, i, 3:7].reshape(-1, 4))
                center = state[:, :, i, :3].reshape(-1, 3) + rot.apply(m.geom_pos[g])
                orient = rot * R.from_quat(np.roll(m.geom_quat[g], -1))
                matrix = orient.as_matrix()
                size = m.geom_size[g]
                kind = m.geom_type[g]
                if kind == mujoco.mjtGeom.mjGEOM_SPHERE:
                    extent = size[0]
                elif kind == mujoco.mjtGeom.mjGEOM_CAPSULE:
                    extent = size[0] + size[1] * abs(matrix[:, 2, 2])
                elif kind == mujoco.mjtGeom.mjGEOM_BOX:
                    extent = abs(matrix[:, 2, :]) @ size
                else:
                    raise ValueError('Unmeasured geometry ' + str(kind))
                lowest = np.minimum(lowest, (center[:, 2] - extent).reshape(lowest.shape))
            per_start = [max(0., -float(lowest[1:int(t)+1, w].min())) for w, t in enumerate(result['ticks'])]
            passes = [i for i, t in enumerate(result['ticks']) if t == 300 and result['peak_target_m'][i] <= .27]
            summary[name] = dict(passes=result['passes'], starts=16, horizon_seconds=10,
                                 mean_seconds=float(np.mean(result['ticks']) / 30),
                                 physics_512_ms=gpu['physics_512_ms'][name],
                                 peak_penetration_m=max(per_start),
                                 peak_penetration_passing_starts_m=max([per_start[i] for i in passes], default=None),
                                 per_start_penetration_m=per_start,
                                 penetration_scope='Exact collider extent at recorded policy ticks through first tracking failure; substep peaks not measured.')
    elapsed = receipt['ended_unix'] - receipt['started_unix']
    report = dict(selected='soft_contact', gpu=summary,
                  physics_overhead_vs_native_default=gpu['physics_512_ms']['soft_contact']/gpu['physics_512_ms']['native_default']-1,
                  billing=dict(pod=receipt['pod'], state=receipt['stop']['state'], elapsed_seconds=elapsed,
                               estimated_gpu_cost=elapsed*.59/3600, authorized_ceiling=.10,
                               cost_note='Rate times measured allocation-to-stop wall time; not the provider invoice.'),
                  limitations=['13/16 is fixed-checkpoint Run LR tracking, not newly trained get-up success.',
                               'Native spherical ball limits approximate, not duplicate, PHAT swing/twist.',
                               'Archived old Run LR body only; current PHAT and recovery starts not revalidated.',
                               'This benchmark measures physics only; no candidate full PPO speed claim.',
                               'Selected profile is not wired into production training yet. Newton coordinate conversions must retain the original policy conventions.'],
                  evidence_sha256=hashlib.sha256((OUT/'gpu-evidence.tar.gz').read_bytes()).hexdigest())
    (OUT / 'audit-summary.json').write_text(json.dumps(report, indent=2))
    profile = dict(name='native_runlr_soft_contact_20261018', status='standalone GPU-validated; production adapter pending',
                   settings=meta['candidates']['soft_contact'], physics_hz=240, policy_hz=30,
                   integrator='implicitfast', solver='Newton', max_iterations=100, max_line_search_iterations=50,
                   tolerance=1e-8, impratio=10, added_armature=0,
                   floor=dict(priority=1, friction=1., condim=3), self_contact=dict(condim=1),
                   gains='unchanged', torque_caps='unchanged', geometry_mass_inertia='unchanged',
                   ball_coordinate_contract=dict(native_q='reference * original_q', native_rest='original_rest * inverse(reference)',
                                                 policy_q='inverse(reference) * native_q', velocity_axes='unchanged child-body axes'),
                   training_launch_authorized=False)
    (OUT / 'selected-profile.json').write_text(json.dumps(profile, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
