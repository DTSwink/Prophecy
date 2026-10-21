"""Fit planted idle hands to the rigid torso without moving pelvis or legs.

Default clearance is zero for the verified planted-hand crawl idle. The crawl
caller supplies authored swing clearances explicitly. Keep source hand XY and
orientation, putting each collision box at the specified clearance above Z=0.
Solve the smallest torso/shoulder/elbow change with exact wrist positions.
"""
import numpy as np
from scipy.optimize import minimize
from scipy.spatial.transform import Rotation as R


def fit_idle(model, frames, wanted, geometry, hand_clearance=None):
    names = model.get_body_names()
    local_p = model._local_translation.numpy().astype(float)
    local_r = R.from_quat(model._local_rotation.numpy()).as_matrix()
    parents = np.asarray(model._parent_indices)
    selected = ['torso', 'right_upper_arm', 'right_lower_arm',
                'left_upper_arm', 'left_lower_arm']
    indices = []
    for name in selected:
        j = model.get_joint(names.index(name))
        indices.extend(range(6+j.dof_idx, 6+j.dof_idx+j.get_dof_dim()))
    indices = np.array(indices)
    hands = [names.index(s+'_hand') for s in ('right', 'left')]
    output = np.array(frames, dtype=float, copy=True)
    targets = wanted[:, hands][:, :, :3, 3].copy()
    for k, j in enumerate(hands):
        g = next(g for g in geometry['shapes'] if g['bone'] == names[j])
        rotation = wanted[:, j, :3, :3]
        # Exact support height of the oriented box, not its centre.
        targets[:, k, 2] = (np.abs((rotation @ np.array(g['axes']))[:, 2, :])
                           @ (np.array(g['dimensions'])/2)
                           - (rotation @ np.array(g['position']))[:, 2])
        if hand_clearance is not None:
            targets[:, k, 2] += hand_clearance[:, k]

    def fk(frame):
        p = np.zeros((len(names), 3)); r = np.zeros((len(names), 3, 3))
        p[0] = frame[:3]; r[0] = R.from_rotvec(frame[3:6]).as_matrix()
        for j in range(1, len(names)):
            joint = model.get_joint(j); width = joint.get_dof_dim()
            d = frame[6+joint.dof_idx:6+joint.dof_idx+width]
            rotation = R.from_rotvec(d if width == 3 else joint.axis.numpy()*d[0]).as_matrix()
            parent = int(parents[j])
            p[j] = p[parent] + r[parent] @ local_p[j]
            r[j] = r[parent] @ local_r[j] @ rotation
        return p, r

    reports = []
    for t, original in enumerate(output.copy()):
        def with_delta(delta):
            f = original.copy(); f[indices] += delta
            return f
        def constraint(delta):
            p, _ = fk(with_delta(delta))
            return (p[hands]-targets[t]).ravel()
        solved = minimize(lambda x: float(x@x), np.zeros(len(indices)),
                          jac=lambda x: 2*x, method='SLSQP',
                          constraints={'type': 'eq', 'fun': constraint},
                          options={'ftol': 1e-12, 'maxiter': 150})
        error = float(np.max(np.abs(constraint(solved.x))))
        if not solved.success or error > 1e-6:
            raise ValueError(f'Idle hand fit failed at {t}: {solved.message}, {error}')
        f = with_delta(solved.x); _, rotations = fk(f)
        # Preserve absolute head and hand orientation after moving their parents.
        for j in [names.index('head'), *hands]:
            joint = model.get_joint(j); assert joint.get_dof_dim() == 3
            f[6+joint.dof_idx:9+joint.dof_idx] = R.from_matrix(
                local_r[j].T @ rotations[int(parents[j])].T @ wanted[t,j,:3,:3]).as_rotvec()
        output[t] = f
        reports.append(dict(frame=t,position_error_m=error,
                            max_coordinate_adjustment_deg=float(np.rad2deg(np.abs(solved.x).max()))))
    # No root, pelvis, or leg change; the rigid body dimensions never change.
    np.testing.assert_array_equal(output[:, :6], frames[:, :6])
    for name in names:
        if any(part in name for part in ('thigh', 'shin', 'foot')):
            joint = model.get_joint(names.index(name)); start = 6+joint.dof_idx
            np.testing.assert_array_equal(output[:,start:start+joint.get_dof_dim()],
                                          frames[:,start:start+joint.get_dof_dim()])
    return output.astype(np.float32), reports
