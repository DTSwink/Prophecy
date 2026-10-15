"""Isolated FBX recovery conversion using the accepted omni retarget/foot cleanup.

Never changes source FBXs, locomotion exports, model, or live training settings.
"""
from pathlib import Path
import hashlib
import json
import pickle
import sys

import numpy as np
import torch
from scipy.spatial.transform import Rotation as R

ROOT = Path(__file__).resolve().parents[2]
STEPPER = Path('C:/Users/singerie/Documents/Cursor/stepper')
sys.path.insert(0, str(STEPPER / 'fbx_npz_pipeline'))
sys.path.insert(0, str(ROOT / 'Tools/Locomotion'))
from fbx_to_npz import load_scene, collect_skeleton_nodes, make_sample_times, get_system_unit
from PrepareMimicKitOmni import matrix, serialized, MJCFCharModel, JointType
from RetargetFootLift import lift_feet, box_bottom


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_fbx(path, source_names):
    manager, scene = load_scene(path)
    try:
        nodes = {n.GetName(): n for n in collect_skeleton_nodes(scene)}
        times, fps, first, last = make_sample_times(scene)
        unit = get_system_unit(scene)
        assert abs(unit['scale_factor_cm'] - 1) < 1e-10, unit
        # Established Stepper FBX Y-up -> UE Z-up mapping. Reflect world Y/Z
        # and local Y together to retain proper rotations, not a mirrored rig.
        world = np.eye(3)[[0, 2, 1]]
        local = np.diag([1., -1., 1.])
        frames = np.tile(np.eye(4), (len(times), len(source_names), 1, 1))
        for t, when in enumerate(times):
            for j, name in enumerate(source_names):
                value = nodes[name].EvaluateGlobalTransform(when)
                p = np.array([value.GetT()[i] for i in range(3)])
                q = np.array([value.GetQ()[i] for i in range(4)])
                scale = np.array([value.GetS()[i] for i in range(3)])
                np.testing.assert_allclose(scale, 1, atol=1e-5)
                frames[t, j, :3, 3] = world @ p * .01
                frames[t, j, :3, :3] = world @ R.from_quat(q).as_matrix() @ local
        assert np.isfinite(frames).all()
        np.testing.assert_allclose(np.linalg.det(frames[:, :, :3, :3]), 1, atol=1e-10)
        return frames, float(fps), [first, last]
    finally:
        manager.Destroy()


def foot_bottoms(names, meta, positions, rotations):
    result = {}
    for side in ('left', 'right'):
        name = side + '_foot'; i = names.index(name)
        rest = serialized(meta['body_frames'][name])
        geom = next(g for g in meta['geometry'] if g['body'] == name)
        local = np.linalg.inv(rest) @ serialized(geom)
        result[side] = np.array([box_bottom(p[i], r[i], local[:3, 3], local[:3, :3], np.array(geom['size'])) for p, r in zip(positions, rotations)])
    return result


def main():
    torch.set_num_threads(1)
    folder = ROOT / 'Labs/MimicKitUEFN'
    output = ROOT / 'Saved/MimicKitRecoveryRetarget'
    viewer = ROOT / 'Labs/MimicKitRecoveryRetarget'
    output.mkdir(parents=True, exist_ok=True); viewer.mkdir(parents=True, exist_ok=True)
    meta = json.loads((folder / 'limits.json').read_text(encoding='utf-8'))
    rig = json.loads((ROOT / 'Saved/Robotics/rig.json').read_text(encoding='utf-8'))
    ref = {b['name']: matrix(b['reference']['position_cm'] + b['reference']['rotation_xyzw']) for b in rig['bodies']}
    source_names = list(ref)
    model = MJCFCharModel('cpu'); model.load(str(folder / 'humanoid_uefn.xml'))
    names = model.get_body_names(); parents = np.asarray(model._parent_indices)
    local_rot = R.from_quat(model._local_rotation.numpy()).as_matrix()
    asset_basis = np.eye(4); asset_basis[:3, :3] = R.from_euler('z', 90, degrees=True).as_matrix()
    motion_basis = np.eye(4); motion_basis[:3, :3] = R.from_euler('z', -90, degrees=True).as_matrix()
    offsets = {n: np.linalg.inv(ref[meta['groups'][n]['anchor']]) @ np.linalg.inv(asset_basis) @ serialized(meta['body_frames'][n]) for n in names}
    previews = []; manifest = []
    files = sorted((STEPPER / 'ue5/slashes/recoveries').glob('*.fbx'))
    assert len(files) == 2, files
    for path in files:
        original_hash = sha(path)
        frames, fps, frame_range = read_fbx(path, source_names)
        wanted = np.stack([motion_basis @ frames[:, source_names.index(meta['groups'][n]['anchor'])] @ offsets[n] for n in names], axis=1)
        count = len(frames); dof = np.zeros((count, 28)); actual_rot = np.zeros((count, len(names), 3, 3)); actual_rot[:, 0] = wanted[:, 0, :3, :3]
        for j in range(1, len(names)):
            parent = int(parents[j]); joint = model.get_joint(j)
            delta = local_rot[j].T @ np.swapaxes(actual_rot[:, parent], -1, -2) @ wanted[:, j, :3, :3]
            if joint.joint_type == JointType.SPHERICAL:
                dof[:, joint.dof_idx:joint.dof_idx+3] = R.from_matrix(delta).as_rotvec(); qr = delta
            elif joint.joint_type == JointType.HINGE:
                q = R.from_matrix(delta).as_quat(); axis = joint.axis.numpy()
                angle = 2*np.arctan2(q[:, :3] @ axis, q[:, 3]); angle = (angle + np.pi) % (2*np.pi) - np.pi
                dof[:, joint.dof_idx] = angle; qr = R.from_rotvec(angle[:, None]*axis).as_matrix()
            else:
                qr = np.broadcast_to(np.eye(3), (count, 3, 3))
            actual_rot[:, j] = actual_rot[:, parent] @ local_rot[j] @ qr
        root_p = wanted[:, 0, :3, 3]; root_q = R.from_matrix(actual_rot[:, 0]).as_quat()
        def fk(values):
            p, q = model.forward_kinematics(torch.tensor(root_p, dtype=torch.float32), torch.tensor(root_q, dtype=torch.float32), model.dof_to_rot(torch.tensor(values, dtype=torch.float32)))
            return p.numpy(), q.numpy()
        before_p, before_q = fk(dof)
        corrections = []; skipped = []
        for tick in range(count):
            saved_dof = dof[tick].copy()
            try:
                found = lift_feet(model, names, meta, wanted[tick:tick+1], before_p[tick:tick+1], actual_rot[tick:tick+1], dof[tick:tick+1])
                for c in found:
                    c['tick'] = tick
                corrections.extend(found)
            except ValueError as error:
                dof[tick] = saved_dof
                # Do not stretch or move a hip for a sub-0.1mm correction on a
                # fully extended leg. Preserve the entire frame and report it.
                # Larger unreachable corrections still stop the conversion.
                original = foot_bottoms(names, meta, wanted[tick:tick+1, :, :3, 3], wanted[tick:tick+1, :, :3, :3])
                before = foot_bottoms(names, meta, before_p[tick:tick+1], actual_rot[tick:tick+1])
                residual = {s: float(max(0, min(original[s][0], 0)-before[s][0])) for s in original}
                if 'Raised foot is unreachable' not in str(error) or max(residual.values()) > 1e-4:
                    raise
                skipped.append(dict(tick=tick, reason=str(error), added_penetration_mm={s: v*1000 for s, v in residual.items()}))
        p, q = fk(dof)
        actual_rot = R.from_quat(q.reshape(-1, 4)).as_matrix().reshape(count, len(names), 3, 3)
        before_rot = R.from_quat(before_q.reshape(-1, 4)).as_matrix().reshape(actual_rot.shape)
        leg_ids = {names.index(side+'_'+part) for side in ('right', 'left') for part in ('thigh', 'shin', 'foot')}
        fixed = [i for i in range(len(names)) if i not in leg_ids]
        np.testing.assert_array_equal(p[:, fixed], before_p[:, fixed]); np.testing.assert_array_equal(q[:, fixed], before_q[:, fixed])
        for side in ('right', 'left'):
            changed = {c['tick'] for c in corrections if c['side'] == side}
            untouched = [t for t in range(count) if t not in changed]
            ids = [names.index(side+'_'+part) for part in ('thigh', 'shin', 'foot')]
            np.testing.assert_array_equal(p[untouched][:, ids], before_p[untouched][:, ids])
            np.testing.assert_array_equal(q[untouched][:, ids], before_q[untouched][:, ids])
        for c in corrections:
            t = c['tick']; fi = names.index(c['side']+'_foot'); ki = names.index(c['side']+'_shin')
            np.testing.assert_allclose(p[t, fi], c['target'], atol=5e-7, rtol=2e-7)
            np.testing.assert_allclose(p[t, ki], c['knee'], atol=5e-7, rtol=2e-7)
            np.testing.assert_allclose(actual_rot[t, fi], before_rot[t, fi], atol=1e-6, rtol=0)
        original_bottom = foot_bottoms(names, meta, wanted[:, :, :3, 3], wanted[:, :, :3, :3])
        before_bottom = foot_bottoms(names, meta, before_p, before_rot)
        after_bottom = foot_bottoms(names, meta, p, actual_rot)
        clearance = {}
        for side in original_bottom:
            extra = np.maximum(0, np.minimum(original_bottom[side], 0) - after_bottom[side])
            regular = [t for t in range(count) if t not in {s['tick'] for s in skipped}]
            assert extra[regular].max() < 1e-6, (side, extra.max())
            assert extra.max() < 1e-4, (side, extra.max())
            clearance[side] = dict(original_min_cm=float(original_bottom[side].min()*100), before_min_cm=float(before_bottom[side].min()*100), after_min_cm=float(after_bottom[side].min()*100), remaining_added_penetration_cm=float(extra.max()*100))
        pos_error = np.linalg.norm(p-wanted[:, :, :3, 3], axis=-1)
        rot_error = np.degrees(R.from_matrix((np.swapaxes(actual_rot, -1, -2) @ wanted[:, :, :3, :3]).reshape(-1, 3, 3)).magnitude()).reshape(count, -1)
        saved = np.concatenate([root_p, R.from_quat(root_q).as_rotvec(), dof], axis=1).astype(np.float32)
        assert np.isfinite(saved).all()
        with (output / (path.stem+'.pkl')).open('wb') as handle:
            pickle.dump(dict(loop_mode=0, fps=fps, frames=saved), handle)
        # Round trip the motion representation into FK, including rotvec roots.
        np.testing.assert_allclose(R.from_rotvec(saved[:, 3:6]).as_matrix(), R.from_quat(root_q).as_matrix(), atol=3e-7)
        label = 'Back get-up' if 'back' in path.stem else 'Front get-up'
        row = dict(id=path.stem, label=label, source=str(path), source_sha256=original_hash, fps=fps, frame_range=frame_range, frames=count, duration=(count-1)/fps, position_max_cm=float(pos_error.max()*100), rotation_max_deg=float(rot_error.max()), foot_lift=dict(corrected_foot_frames=len(corrections), max_cm=max((c['lift_cm'] for c in corrections), default=0.)), clearance=clearance, per_body_position_max_cm=dict(zip(names, (pos_error.max(0)*100).tolist())), per_body_rotation_max_deg=dict(zip(names, rot_error.max(0).tolist())))
        row['foot_lift']['uncorrected_submillimetre_frames'] = skipped
        manifest.append(row)
        source_frames = motion_basis @ frames
        source_pose = np.concatenate([source_frames[:, :, :3, 3], R.from_matrix(source_frames[:, :, :3, :3].reshape(-1, 3, 3)).as_quat().reshape(count, -1, 4)], axis=-1)
        previews.append(dict(id=path.stem, label=label, source=np.round(source_pose, 7).tolist(), reduced=np.round(np.concatenate([p, q], axis=-1), 7).tolist(), metrics=row))
        np.savez_compressed(output / (path.stem+'.npz'), source=source_pose, before=np.concatenate([before_p, before_q], axis=-1), reduced=np.concatenate([p, q], axis=-1), frames=saved, fps=fps)
        (output / (path.stem+'-foot-corrections.json')).write_text(json.dumps(corrections, indent=2), encoding='utf-8')
        assert sha(path) == original_hash
        print(json.dumps(row), flush=True)
    overlay = json.loads((folder/'overlay-data.json').read_text(encoding='utf-8'))
    def local_geometry(layer, rest):
        result = []
        for g in overlay[layer]:
            body = g['name'].rsplit('_shape', 1)[0] if layer == 'phat' else g['body']
            local = np.linalg.inv(serialized(rest[body])) @ serialized(g)
            result.append(dict(g, body=body, position=local[:3, 3].tolist(), quaternion=R.from_matrix(local[:3, :3]).as_quat().tolist()))
        return result
    assert all(c['metrics']['fps'] == fps for c in previews)
    payload = dict(fps=fps, names=names, source_names=source_names, clips=previews, geometry=local_geometry('new', meta['body_frames']), source_geometry=local_geometry('phat', overlay['meta']['source_body_frames']))
    (viewer/'recovery-preview.json').write_text(json.dumps(payload, separators=(',', ':')), encoding='utf-8')
    dependencies = [folder/'humanoid_uefn.xml', folder/'limits.json', ROOT/'Tools/Locomotion/RetargetFootLift.py', Path(__file__)]
    (output/'manifest.json').write_text(json.dumps(dict(status='retargeted_candidates_for_review_not_training', loop_mode='CLAMP', inputs_unchanged=True, dependencies={str(p): sha(p) for p in dependencies}, motions=manifest), indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
