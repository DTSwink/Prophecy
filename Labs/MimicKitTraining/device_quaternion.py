"""Same rotation formulas as upstream, without TorchScript's CPU constants."""
import torch


def normalize(value):
    return value / value.norm(p=2, dim=-1).clamp(min=1e-9).unsqueeze(-1)


def axis_angle_to_quat(axis, angle):
    theta = (angle / 2).unsqueeze(-1)
    return normalize(torch.cat((normalize(axis) * theta.sin(), theta.cos()), -1))


def exp_map_to_quat(value):
    angle = torch.norm(value, dim=-1)
    axis = value / angle.unsqueeze(-1)
    angle = torch.atan2(torch.sin(angle), torch.cos(angle))
    default_axis = torch.zeros_like(value)
    default_axis[..., -1] = 1
    mask = angle.abs() > 1e-5
    angle = torch.where(mask, angle, torch.zeros_like(angle))
    axis = torch.where(mask.unsqueeze(-1), axis, default_axis)
    return axis_angle_to_quat(axis, angle)


def quat_to_axis_angle(q):
    q = (1-2*(q[..., 3:] < 0).float())*q
    length = torch.norm(q[..., :3], dim=-1, p=2)
    angle = 2*torch.atan2(length, q[..., 3])
    axis = q[..., :3]/length.unsqueeze(-1)
    default = torch.zeros_like(axis)
    default[..., -1] = 1
    mask = length > 1e-5
    return (torch.where(mask.unsqueeze(-1), axis, default),
            torch.where(mask, angle, torch.zeros_like(angle)))


def quat_to_exp_map(q):
    axis, angle = quat_to_axis_angle(q)
    return axis*angle.unsqueeze(-1)


def quat_twist_angle(q, twist_axis):
    projection = (twist_axis*q[..., :3]).sum(-1)
    twist = q.clone()
    twist[..., :3] = projection.unsqueeze(-1)*twist_axis
    twist = normalize((1-2*(twist[..., 3:] < 0).float())*twist)
    axis, angle = quat_to_axis_angle(twist)
    return torch.where((twist_axis*axis).sum(-1) < 0, -angle, angle)


def quat_rotate(q, v):
    xyz, w = q[..., :3], q[..., -1:]
    t = 2 * torch.cross(xyz, v, dim=-1)
    return v + w * t + torch.cross(xyz, t, dim=-1)


def quat_mul(a, b):
    x1, y1, z1, w1 = a.unbind(-1)
    x2, y2, z2, w2 = b.unbind(-1)
    ww = (z1+x1)*(x2+y2)
    yy = (w1-y1)*(w2+z2)
    zz = (w1+y1)*(w2-z2)
    xx = ww+yy+zz
    qq = .5*(xx+(z1-x1)*(x2-y2))
    return torch.stack((qq-xx+(x1+w1)*(x2+w2), qq-yy+(w1-x1)*(y2+z2),
                        qq-zz+(z1+y1)*(w2-x2), qq-ww+(z1-y1)*(y2-z2)), -1)


def heading_inverse(q):
    ref = torch.zeros_like(q[..., :3])
    ref[..., 0] = 1
    rotated = quat_rotate(q, ref)
    heading = torch.atan2(rotated[..., 1], rotated[..., 0])
    axis = torch.zeros_like(ref)
    axis[..., 2] = 1
    return axis_angle_to_quat(axis, -heading)


def tan_norm(q):
    tan = torch.zeros_like(q[..., :3])
    tan[..., 0] = 1
    normal = torch.zeros_like(tan)
    normal[..., -1] = 1
    return torch.cat((quat_rotate(q, tan), quat_rotate(q, normal)), -1)


def physical_observations(root, rot, vel, ang, joints, dof_vel, keys,
                          global_obs, root_height):
    heading = heading_inverse(rot)
    root_rot = tan_norm(rot if global_obs else quat_mul(heading, rot))
    local_vel = vel if global_obs else quat_rotate(heading, vel)
    local_ang = ang if global_obs else quat_rotate(heading, ang)
    joint_obs = tan_norm(joints.reshape(-1, 4)).reshape(joints.shape[0], -1)
    pieces = [root_rot, local_vel, local_ang, joint_obs, dof_vel]
    if len(keys):
        keys = keys-root.unsqueeze(-2)
        if not global_obs:
            # Match upstream's repeated heading calculation and operation order.
            h = heading_inverse(rot).unsqueeze(-2).repeat(1, keys.shape[1], 1)
            keys = quat_rotate(h.reshape(-1, 4), keys.reshape(-1, 3)).reshape_as(keys)
        pieces.append(keys.reshape(keys.shape[0], -1))
    if root_height:
        pieces.insert(0, root[:, 2:3])
    return torch.cat(pieces, -1)
