"""Opt-in batched equivalent of MimicKit's per-joint quaternion conversions."""
import types
import torch
import device_quaternion as device_q


def install(model):
    if getattr(model, '_batched_joint_conversion', False):
        return
    hinge, sphere = [], []
    for j in range(1, model.get_num_joints()):
        joint = model.get_joint(j)
        kind = joint.joint_type.name
        if kind == 'HINGE':
            hinge.append((j - 1, joint.dof_idx, joint.axis))
        elif kind == 'SPHERICAL':
            sphere.append((j - 1, joint.dof_idx))
        elif kind not in ('FIXED', 'ROOT'):
            raise ValueError(f'Unsupported joint type: {kind}')
    device = model._device
    hi = torch.tensor([x[0] for x in hinge], device=device, dtype=torch.long)
    hd = torch.tensor([x[1] for x in hinge], device=device, dtype=torch.long)
    axes = torch.stack([x[2] for x in hinge]) if hinge else None
    si = torch.tensor([x[0] for x in sphere], device=device, dtype=torch.long)
    sd = torch.tensor([[x[1]+k for k in range(3)] for x in sphere],
                      device=device, dtype=torch.long).reshape(-1, 3)
    joints, dofs = model.get_num_joints()-1, model.get_dof_size()

    def dof_to_rot(self, values):
        result = values.new_zeros((*values.shape[:-1], joints, 4))
        result[..., 3] = 1
        if hinge:
            result[..., hi, :] = device_q.axis_angle_to_quat(
                axes.expand(*values.shape[:-1], len(hinge), 3), values[..., hd])
        if sphere:
            result[..., si, :] = device_q.exp_map_to_quat(values[..., sd])
        return result

    def rot_to_dof(self, rotations):
        result = rotations.new_zeros((*rotations.shape[:-2], dofs))
        if hinge:
            result[..., hd] = device_q.quat_twist_angle(rotations[..., hi, :], axes)
        if sphere:
            result[..., sd] = device_q.quat_to_exp_map(rotations[..., si, :])
        return result

    model.dof_to_rot = types.MethodType(dof_to_rot, model)
    model.rot_to_dof = types.MethodType(rot_to_dof, model)
    model._batched_joint_conversion = True
