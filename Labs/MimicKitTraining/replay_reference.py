"""CPU-only reference reconstruction for legacy stock walking captures.

Stock DeepMimic resets exactly onto its motion. Recover the unique phase from
that initial full pose; reject mismatches instead of displaying a guessed target.
No fitting to later simulated frames and no realignment to the falling actor.
"""
from functools import lru_cache
from pathlib import Path
import sys
import numpy as np


@lru_cache(maxsize=1)
def walking_motion():
    repo = Path(__file__).resolve().parents[2] / 'Saved/MimicKit/vendor/MimicKit'
    sys.path.insert(0, str(repo / 'mimickit'))
    import torch
    from anim.mjcf_char_model import MJCFCharModel
    from anim.motion_lib import MotionLib
    torch.set_num_threads(1)
    model = MJCFCharModel('cpu')
    model.load(str(repo / 'data/assets/humanoid/humanoid.xml'))
    motion = MotionLib(str(repo / 'data/motions/humanoid/humanoid_walk.pkl'), model, 'cpu')
    return torch, model, motion


def recover_walk_reference(meta, pose, data, run):
    if meta.get('task') not in (None, 'deepmimic_walk') or 'walk' not in run.lower():
        return None
    torch, model, motion = walking_motion()
    if list(model.get_body_names()) != meta['names']:
        return None
    roots = motion._frame_root_pos.numpy()
    segments = np.diff(roots, axis=0)
    squared = (segments * segments).sum(axis=1)
    valid = squared > 1e-12
    blend = ((pose[0, 0, :3] - roots[:-1]) * segments).sum(axis=1) / np.maximum(squared, 1e-12)
    candidates = np.flatnonzero(valid & (blend >= -1e-5) & (blend <= 1 + 1e-5))
    if not len(candidates):
        return None
    times = torch.tensor((candidates + np.clip(blend[candidates], 0, 1)) / float(motion._motion_fps[0]), dtype=torch.float32)
    ids = torch.zeros(len(times), dtype=torch.long)
    root, rotation, _, _, joints, _ = motion.calc_motion_frame(ids, times)
    positions, rotations = model.forward_kinematics(root, rotation, joints)
    position_error = np.linalg.norm(positions.numpy() - pose[0, :, :3], axis=-1).max(axis=1)
    q = rotations.numpy(); target = pose[0, :, 3:]
    rotation_error = np.minimum(np.linalg.norm(q-target, axis=-1), np.linalg.norm(q+target, axis=-1)).max(axis=1)
    # Reset converts reference quaternions to joint DOFs and back. Float32
    # round-trip error is measurable at the feet; allow 0.1 mm / ~0.012 deg.
    matches = np.flatnonzero((position_error < 1e-4) & (rotation_error < 1e-4))
    if not len(matches) or np.ptp(times[matches].numpy()) > 2e-6:
        return None
    selected = matches[np.argmin(position_error[matches] + rotation_error[matches])]
    start = times[selected].item()
    times = torch.tensor(data[:, 1], dtype=torch.float32) + start
    root, rotation, _, _, joints, _ = motion.calc_motion_frame(torch.zeros(len(times), dtype=torch.long), times)
    positions, rotations = model.forward_kinematics(root, rotation, joints)
    reference = np.concatenate([positions.numpy(), rotations.numpy()], axis=-1)
    assert np.isfinite(reference).all()
    return reference, dict(source='stock walking motion, unique full-reset-pose match',
        start_time_seconds=start, initial_max_position_error_m=float(position_error[selected]),
        initial_max_quaternion_error=float(rotation_error[selected]))
