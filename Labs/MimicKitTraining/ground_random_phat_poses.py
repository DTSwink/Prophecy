"""Bake random whole-body orientations at the lowest nonpenetrating height."""
import hashlib
import itertools
import json
from pathlib import Path
import sys

import numpy as np
from scipy.spatial.transform import Rotation as R
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'Labs/CrawlTraining'), str(ROOT/'Labs/MimicKitUEFN'),
               str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit')]
from current_phat import current_source
from anim.mjcf_char_model import MJCFCharModel


def floor_heights(poses, bodies, corners=False):
    """Exact support of every box, capsule or sphere against the Z=0 plane."""
    heights = []
    for i, body in enumerate(bodies):
        rotation = R.from_quat(poses[:, i, 3:])
        for shape in body['shapes']:
            centre = poses[:, i, :3] + rotation.apply(shape['pos'])
            world = rotation * R.from_quat(shape['quat'])
            size = np.asarray(shape['size'])
            if shape['type'] == 'box':
                if corners:
                    vertices = np.asarray(list(itertools.product([-1, 1], repeat=3))) * size
                    z = np.einsum('nij,kj->nki', world.as_matrix(), vertices)[:, :, 2]
                    low = centre[:, 2] + z.min(axis=1)
                else:
                    low = centre[:, 2] - np.abs(world.as_matrix()[:, 2]) @ size
            elif shape['type'] == 'capsule':
                axis = world.apply([0., 0., size[1]])[:, 2]
                low = np.minimum(centre[:, 2] + axis, centre[:, 2] - axis) - size[0]
            elif shape['type'] == 'sphere':
                low = centre[:, 2] - size[0]
            else:
                raise ValueError(f"Unsupported collider: {shape['type']}")
            heights.append(low)
    return np.stack(heights, axis=1)


def main():
    meta = current_source()
    source = ROOT/'Saved/MimicKitEquipment/random-phat-poses'
    output = ROOT/'Saved/MimicKitEquipment/random-phat-poses-grounded'
    output.mkdir(exist_ok=True)
    data = json.loads((source/'data.json').read_text(encoding='utf-8'))
    arrays = dict(np.load(source/'corpus.npz', allow_pickle=False))
    assert len(arrays['dof']) == 1000
    assert data['report']['source_files'] == meta['source_files']
    torch.set_num_threads(1)
    model = MJCFCharModel('cpu')
    model.load(str(ROOT/'Labs/MimicKitUEFN/humanoid_uefn.xml'))
    assert list(arrays['body_names']) == model.get_body_names()
    seed = 20261021
    # Haar-uniform SO(3), not independent Euler angles (which bias orientation).
    rotations = R.random(1000, random_state=np.random.default_rng(seed))
    root_quat = rotations.as_quat().astype(np.float32)
    root_pos = np.zeros((1000, 3), np.float32)
    local_rot = model.dof_to_rot(torch.from_numpy(arrays['dof']))

    def fk():
        with torch.no_grad():
            pos, quat = model.forward_kinematics(torch.from_numpy(root_pos),
                                                torch.from_numpy(root_quat), local_rot)
        return torch.cat((pos, quat), -1).numpy()

    zero_pose = fk()
    minimum_height = -floor_heights(zero_pose, data['bodies']).min(axis=1)
    root_pos[:, 2] = minimum_height
    # Recheck the baked float32 FK. Only upward roundoff correction, no padding.
    for _ in range(8):
        poses = fk()
        clearance = floor_heights(poses, data['bodies']).min(axis=1)
        below = clearance < 0
        if not below.any():
            break
        root_pos[below, 2] = np.nextafter(
            (root_pos[below, 2].astype(np.float64) - clearance[below]).astype(np.float32),
            np.float32(np.inf))
    else:
        raise RuntimeError('Could not eliminate float32 floor penetration')

    independent = floor_heights(poses, data['bodies'], corners=True)
    minimum = independent.min(axis=1)
    assert np.all(minimum >= 0)
    assert np.all(minimum < 1e-6), 'A pose is not at its minimal floor height'
    lowered = poses.copy()
    lowered[:, :, 2] -= np.float32(1e-6)
    assert np.all(floor_heights(lowered, data['bodies'], corners=True).min(axis=1) < 0)
    # A root transform must not alter the articulated pose.
    old_relative = arrays['body_pose_xyz_xyzw'][:, :, :3] - arrays['root_position'][:, None, :]
    expected = np.stack([r.apply(p) for r, p in zip(R.from_quat(root_quat), old_relative)])
    actual = poses[:, :, :3] - root_pos[:, None, :]
    rigid_error = float(np.max(np.linalg.norm(expected - actual, axis=-1)))
    assert rigid_error < 2e-6
    np.testing.assert_array_equal(poses[:, 0, :3], root_pos)
    np.testing.assert_array_equal(poses[:, 0, 3:], root_quat)
    arrays.update(root_position=root_pos, root_quaternion_xyzw=root_quat,
                  body_pose_xyz_xyzw=poses, minimum_floor_clearance_m=minimum)
    path = output/'corpus.npz'
    np.savez_compressed(path, **arrays)
    with np.load(path) as saved:
        np.testing.assert_array_equal(saved['dof'], np.load(source/'corpus.npz')['dof'])
        np.testing.assert_array_equal(saved['body_pose_xyz_xyzw'], poses)
    report = dict(data['report'])
    report.pop('pelvis_position_m', None)
    report.pop('pelvis_quaternion_xyzw', None)
    report.update(
        name='stiff inits',
        source_corpus_sha256=hashlib.sha256((source/'corpus.npz').read_bytes()).hexdigest(),
        corpus_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        root_rotation_seed=seed,
        root_rotation_sampling='Independent uniform SO(3) orientations; whole body rotates about pelvis.',
        collision_processing='Exact collider support against Z=0; minimal root Z with float32 upward roundoff only. Self-overlap unchanged.',
        poses_below_floor=0,
        pelvis_height_range_m=[float(root_pos[:, 2].min()), float(root_pos[:, 2].max())],
        floor_clearance_range_m=[float(minimum.min()), float(minimum.max())],
        max_rigid_transform_error_m=rigid_error,
        minimality_check='Every pose penetrates if translated down 1 micrometre.',
        training_deployed=False)
    (output/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (output/'data.json').write_text(json.dumps(dict(report=report, bodies=data['bodies'],
        poses=poses.tolist(), minimum_floor_clearance_m=minimum.tolist()), separators=(',', ':')),
        encoding='utf-8')
    html = (source/'index.html').read_text(encoding='utf-8')
    html = html.replace('Random PHAT poses', 'Stiff inits')
    html = html.replace('pelvis fixed and upright', 'random whole-body rotation · grounded colliders')
    html = html.replace('These are raw joint-limit samples: floor contact and self-overlap have not been cleaned.',
                        'Each pose is at its lowest nonpenetrating pelvis height. Self-overlap is unchanged.')
    (output/'index.html').write_text(html, encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['count', 'poses_below_floor', 'pelvis_height_range_m',
        'floor_clearance_range_m', 'max_rigid_transform_error_m', 'corpus_sha256']}, indent=2))


if __name__ == '__main__':
    main()
