"""Bake 10 policy frames of unactuated native-MuJoCo settling from stiff inits."""
import os
os.environ['PYGLET_HEADLESS'] = 'true'
os.environ['OMP_NUM_THREADS'] = '1'
import hashlib
import json
from pathlib import Path
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'Saved/MimicKitUEFN/dependencies'),
               str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit'),
               str(ROOT/'Labs/CrawlTraining'), str(ROOT/'Labs/MimicKitUEFN')]
import mujoco
import numpy as np
from scipy.spatial.transform import Rotation as R
import torch
import warp as wp
import yaml
from audit_getup_strength import CpuEngine
from engines.engine import ObjType
from anim.mjcf_char_model import MJCFCharModel
from current_phat import current_source
from ground_random_phat_poses import floor_heights
from util import mp_util


def main():
    started = time.monotonic()
    meta = current_source()
    src = ROOT/'Saved/MimicKitEquipment/random-phat-poses-grounded'
    out = ROOT/'Saved/MimicKitEquipment/limp-inits'
    out.mkdir(exist_ok=True)
    arrays = dict(np.load(src/'corpus.npz', allow_pickle=False))
    view = json.loads((src/'data.json').read_text(encoding='utf-8'))
    assert view['report']['source_files'] == meta['source_files']
    with zipfile.ZipFile(ROOT/'Saved/MimicKitEquipment/normal-back80-source.zip') as z:
        cfg = yaml.safe_load(z.read('prepared/engine_config.yaml'))
    cfg['uefn_asset_directory'] = str(ROOT/'Labs/MimicKitUEFN')
    torch.set_num_threads(1)
    wp.init()
    wp.set_device('cpu')
    mp_util.init(0, 1, 'cpu', 6789)
    engine = CpuEngine(cfg, 1, 'cpu', False)
    env = engine.create_env()
    engine.create_obj(env, ObjType.articulated,
                      str(ROOT/'Labs/MimicKitUEFN/humanoid_uefn.xml'), 'character')
    engine.initialize_sim()
    m, d = engine._solver.mj_model, engine._solver.mj_data
    # Disable all actuator forces, including velocity-servo damping.
    m.opt.disableflags |= int(mujoco.mjtDisableBit.mjDSBL_ACTUATION)
    assert np.max(np.abs(m.jnt_stiffness)) == 0
    assert np.max(np.abs(m.dof_damping)) == 0
    assert abs(m.opt.timestep - 1/240) < 1e-12
    assert np.allclose(m.opt.gravity, [0, 0, -9.81])
    names = list(arrays['body_names'])
    ids = [next(b for b in range(1, m.nbody) if m.body(b).name.endswith(n)) for n in names]
    kin = MJCFCharModel('cpu')
    kin.load(str(ROOT/'Labs/MimicKitUEFN/humanoid_uefn.xml'))
    refs = {j['body']: R.from_quat(np.roll(j['reference_wxyz'], -1))
            for j in meta['joints'] if j['kind'] == 'ball'}
    snapshots, qposes, qvels, dofs, joint_vels, world_vels = [], [], [], [], [], []
    initial_error = 0.
    warning_counts = np.zeros(len(d.warning), dtype=np.int64)
    for row, initial in enumerate(arrays['body_pose_xyz_xyzw']):
        mujoco.mj_resetData(m, d)
        d.qpos[:3] = initial[0, :3]
        d.qpos[3:7] = np.roll(initial[0, 3:], 1)
        rotations = R.from_quat(initial[:, 3:])
        for i, b in enumerate(ids[1:], 1):
            parent = ids.index(m.body_parentid[b])
            j = m.body_jntadr[b]
            qa = m.jnt_qposadr[j]
            relative = R.from_quat(np.roll(m.body_quat[b], -1)).inv() * rotations[parent].inv() * rotations[i]
            if m.jnt_type[j] == mujoco.mjtJoint.mjJNT_BALL:
                d.qpos[qa:qa+4] = np.roll(relative.as_quat(), 1)
            else:
                d.qpos[qa] = relative.as_rotvec() @ m.jnt_axis[j]
        mujoco.mj_forward(m, d)
        initial_error = max(initial_error, float(np.abs(d.xpos[ids] - initial[:, :3]).max()))
        assert initial_error < 2e-6
        for _ in range(80):
            mujoco.mj_step(m, d)
        assert abs(d.time - 10/30) < 1e-12, 'A simulation reset unexpectedly'
        mujoco.mj_forward(m, d)
        assert not np.any(d.qfrc_actuator)
        assert np.isfinite(d.qpos).all() and np.isfinite(d.qvel).all()
        warning_counts += np.asarray([w.number for w in d.warning])
        pose = np.concatenate((d.xpos[ids], d.xquat[ids][:, [1, 2, 3, 0]]), axis=1)
        values = np.zeros(34, np.float32)
        velocities = np.zeros(34, np.float32)
        for i, b in enumerate(ids[1:], 1):
            j = m.body_jntadr[b]
            qa, va = m.jnt_qposadr[j], m.jnt_dofadr[j]
            target = kin.get_joint(i)
            k = target.dof_idx
            if m.jnt_type[j] == mujoco.mjtJoint.mjJNT_BALL:
                q = R.from_quat(np.roll(d.qpos[qa:qa+4], -1))
                values[k:k+3] = (refs[names[i]].inv() * q).as_rotvec()
                velocities[k:k+3] = d.qvel[va:va+3]
            else:
                values[k] = d.qpos[qa]
                velocities[k] = d.qvel[va]
        # Explicit body-origin linear and world angular velocities.
        speeds = []
        for b in ids:
            jp = np.zeros((3, m.nv))
            jr = np.zeros((3, m.nv))
            mujoco.mj_jacBody(m, d, jp, jr, b)
            speeds.append(np.r_[jp @ d.qvel, jr @ d.qvel])
        snapshots.append(pose)
        qposes.append(d.qpos.copy())
        qvels.append(d.qvel.copy())
        dofs.append(values)
        joint_vels.append(velocities)
        world_vels.append(speeds)
        if (row + 1) % 250 == 0:
            print(f'Settled {row+1}/1000 poses', flush=True)
    assert not warning_counts.any(), f'Physics warnings: {warning_counts}'
    poses = np.asarray(snapshots, np.float32)
    values = np.asarray(dofs)
    speeds = np.asarray(world_vels, np.float32)
    with torch.no_grad():
        p, q = kin.forward_kinematics(torch.from_numpy(poses[:, 0, :3].copy()),
                                     torch.from_numpy(poses[:, 0, 3:].copy()),
                                     kin.dof_to_rot(torch.from_numpy(values)))
    fk_error = float(np.abs(p.numpy() - poses[:, :, :3]).max())
    assert fk_error < 3e-6
    angle_error = (R.from_quat(q.numpy().reshape(-1, 4)).inv() *
                   R.from_quat(poses[:, :, 3:].reshape(-1, 4))).magnitude().max()
    assert angle_error < 1e-5
    minimum = floor_heights(poses, view['bodies'], corners=True).min(axis=1)
    path = out/'corpus.npz'
    np.savez_compressed(path, dof=values, root_position=poses[:, 0, :3],
        root_quaternion_xyzw=poses[:, 0, 3:], body_pose_xyz_xyzw=poses,
        dof_velocity=np.asarray(joint_vels), root_linear_velocity=speeds[:, 0, :3],
        root_angular_velocity=speeds[:, 0, 3:], body_velocity_world=speeds,
        body_names=arrays['body_names'], minimum_floor_clearance_m=minimum,
        native_qpos=np.asarray(qposes), native_qvel=np.asarray(qvels),
        source_pose_index=np.arange(1000))
    mujoco.mj_saveModel(m, str(out/'settling-model.mjb'), None)
    report = dict(name='limp inits', count=1000, source_name='stiff inits',
        source_corpus_sha256=hashlib.sha256((src/'corpus.npz').read_bytes()).hexdigest(),
        corpus_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        source_files=meta['source_files'], policy_frames=10, policy_hz=30,
        physics_steps=80, physics_hz=240, duration_seconds=10/30,
        backend='Configured native MuJoCo CPU, training model construction/profile',
        actuators='Disabled entirely; no velocity-servo resistance',
        gravity=m.opt.gravity.tolist(), self_collision='Same exclusions/contact settings as training',
        velocities='Actual velocities at snapshot; native qpos/qvel also saved',
        postprocessing='None: exact simulated frame-10 pose, no floor lift or joint projection',
        floor_clearance_range_m=[float(minimum.min()), float(minimum.max())],
        poses_with_floor_penetration_over_1mm=int((minimum < -.001).sum()),
        initial_pose_max_error_m=initial_error, exported_fk_max_error_m=fk_error,
        exported_rotation_error_rad=float(angle_error), physics_warnings=warning_counts.tolist(),
        training_deployed=False, wall_seconds=time.monotonic()-started)
    (out/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (out/'data.json').write_text(json.dumps(dict(report=report, bodies=view['bodies'],
        poses=poses.tolist(), minimum_floor_clearance_m=minimum.tolist()), separators=(',', ':')),
        encoding='utf-8')
    html = (src/'index.html').read_text(encoding='utf-8')
    html = html.replace('Random PHAT poses', 'Limp inits').replace('Stiff inits', 'Limp inits').replace('PHAT ✓', 'Frame 10')
    html = html.replace('1,000 independent poses · random whole-body rotation · grounded colliders',
                        '1,000 limp inits · 10 frames / ⅓ second · motors off')
    html = html.replace('Each pose is at its lowest nonpenetrating pelvis height. Self-overlap is unchanged.',
                        'Exact simulated poses after gravity and contact. No pose correction after simulation.')
    (out/'index.html').write_text(html, encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
