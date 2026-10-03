"""Angular-speed hinge on reconstructed hand orientation in forearm space.

All bases use the native row-axis convention. Measure AFTER the full decoder's
baseline/deviation transport, never directly on the agent's hand rot6 output.
"""
import math
import torch
from collision_objective import _matrix_to_quaternion

THRESHOLD_DEG_S=400.
FPS=30.
CONTRACT='reconstructed_hand_in_forearm_geodesic_mean_hinge_400deg_s_v1'


def wrist_angular_velocity_frames(rotations,times,hand_indices,forearm_indices,valid):
    """Return B,controlled-interval,2 deg/s and B,interval mean excess.

    Exclude the uncontrollable primer transition 0->1. Source times are in
    30-FPS frames, including the final fractional frame; padding contributes 0.
    """
    hands=rotations.index_select(2,hand_indices)
    forearms=rotations.index_select(2,forearm_indices)
    local=hands @ forearms.transpose(-1,-2)
    change=local[:,2:] @ local[:,1:-1].transpose(-1,-2)
    quaternion=_matrix_to_quaternion(change)
    # atan2 avoids acos's singular gradients at identity and at pi. Quaternion
    # sign is immaterial; this is the shortest SO(3) angle, not Euler differences.
    angle=2*torch.atan2(torch.linalg.vector_norm(quaternion[...,1:],dim=-1),quaternion[...,0].abs())
    dt=(times[:,2:]-times[:,1:-1])/FPS
    dt=torch.where(valid,dt,torch.ones_like(dt)).clamp_min(1e-12)
    speed=angle*(180./math.pi)/dt[...,None]
    speed=torch.where(valid[...,None],speed,0.)
    return speed,torch.relu(speed-THRESHOLD_DEG_S).mean(-1)
