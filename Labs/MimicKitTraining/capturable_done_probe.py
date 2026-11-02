"""Pinned rules with scalar boolean writes expressed as masked fills."""
import torch
from torch import Tensor
from typing import Optional
from envs import base_env, char_env

@torch.jit.script
def compute_done_capturable(done_buf, time, ep_len, root_rot, body_pos, tar_root_rot, tar_body_pos, 
                 ground_contact_force, contact_body_ids,
                 pose_termination, pose_termination_dist, 
                 global_obs, enable_early_termination,
                 motion_times, motion_len, motion_len_term,
                 track_root, pose_termination_mask=None):
    # type: (Tensor, Tensor, float, Tensor, Tensor, Tensor, Tensor, Tensor, Tensor, bool, float, bool, bool, Tensor, Tensor, Tensor, bool, Optional[Tensor]) -> Tensor
    done = torch.full_like(done_buf, base_env.DoneFlags.NULL.value)
    
    timeout = time >= ep_len
    done.masked_fill_(timeout, base_env.DoneFlags.TIME.value)
    
    motion_end = motion_times >= motion_len
    motion_end = torch.logical_and(motion_end, motion_len_term)
    done.masked_fill_(motion_end, base_env.DoneFlags.SUCC.value)

    if (enable_early_termination):
        failed = torch.zeros(done.shape, device=done.device, dtype=torch.bool)

        if (contact_body_ids.shape[0] > 0):
            masked_contact_buf = ground_contact_force.detach().clone()
            masked_contact_buf.index_fill_(1, contact_body_ids, 0)
            fall_contact = torch.any(torch.abs(masked_contact_buf) > 0.1, dim=-1)

            has_fallen = torch.any(fall_contact, dim=-1)
            failed = torch.logical_or(failed, has_fallen)

        if (pose_termination):
            root_pos = body_pos[..., 0:1, :]
            tar_root_pos = tar_body_pos[..., 0:1, :]

            if (not global_obs):
                body_pos = body_pos[..., 1:, :] - root_pos
                tar_body_pos = tar_body_pos[..., 1:, :] - tar_root_pos
                body_pos = char_env.convert_to_local_root_body_pos(root_rot, body_pos)
                tar_body_pos = char_env.convert_to_local_root_body_pos(tar_root_rot, tar_body_pos)

            elif (not track_root):
                body_pos = body_pos[..., 1:, :] - root_pos
                tar_body_pos = tar_body_pos[..., 1:, :] - tar_root_pos

            body_pos_diff = tar_body_pos - body_pos
            body_pos_dist = torch.sum(body_pos_diff * body_pos_diff, dim=-1)
            body_pos_dist = torch.max(body_pos_dist, dim=-1)[0]
            pose_fail = body_pos_dist > pose_termination_dist * pose_termination_dist

            if (track_root):
                root_pos_diff = tar_root_pos - root_pos
                root_pos_dist = torch.sum(root_pos_diff * root_pos_diff, dim=-1)
                root_pos_fail = root_pos_dist > pose_termination_dist * pose_termination_dist
                root_pos_fail = root_pos_fail.squeeze(-1)
                pose_fail = torch.logical_or(pose_fail, root_pos_fail)

            if pose_termination_mask is not None:
                pose_fail = pose_fail & pose_termination_mask
            failed = torch.logical_or(failed, pose_fail)
            
        # only fail after first timestep
        not_first_step = (time > 0.0)
        failed = torch.logical_and(failed, not_first_step)
        done.masked_fill_(failed, base_env.DoneFlags.FAIL.value)
    
    return done
