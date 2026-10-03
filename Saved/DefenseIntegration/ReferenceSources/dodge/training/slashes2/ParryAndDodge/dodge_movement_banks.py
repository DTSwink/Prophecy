"""Portable, tensor-only path budgets and causal extrapolated root commands.

Units are metres/radians per action, not speeds or Euler angles. A return trip
spends the same budget as the outward trip. No Python mutable episode state.
"""
from dataclasses import dataclass
import math
import torch

CONTRACT = 'dodge_live_lower_remaining_banks_root_yaw_v2'
BANK_NAMES = ('pelvis_horizontal','left_foot_xyz','right_foot_xyz','pelvis_rotation','root_horizontal','root_yaw')
ACTION_DIM = 22
DEFAULT_LIMITS = (.30,.30,.30,math.pi/4,.30,math.pi/4)
GATE_INDICES = (2,6,10,14,17,19,21)


def limits_for_families(families, overrides=None, *, device='cpu'):
    overrides=overrides or {}
    values=[]
    for family in families:
        entry=dict(zip(BANK_NAMES,DEFAULT_LIMITS));entry.update(overrides.get(family,{}))
        if set(entry)!=set(BANK_NAMES) or any(not math.isfinite(v) or v<0 for v in entry.values()):
            raise ValueError(f'Invalid movement-bank configuration for {family}')
        values.append([entry[k] for k in BANK_NAMES])
    return torch.tensor(values,dtype=torch.float32,device=device)


def spend(vector, gate, remaining, *, return_request=False):
    requested=vector*gate.clamp(0.,1.)
    distance=torch.linalg.vector_norm(requested,dim=-1,keepdim=True)
    scale=torch.minimum(torch.ones_like(distance),remaining.clamp_min(0.)/distance.clamp_min(1e-8))
    applied=requested*scale
    # Charge the clipped path length directly. Re-measuring the normalized
    # float32 vector can leave a tiny positive residue after full exhaustion,
    # which would incorrectly keep the pose gate enabled on the next step.
    used=torch.minimum(distance,remaining.clamp_min(0.))
    result=(applied,(remaining-used).clamp_min(0.))
    return (*result,distance) if return_request else result


@dataclass
class Controls:
    pelvis_horizontal: torch.Tensor
    left_foot: torch.Tensor
    right_foot: torch.Tensor
    pelvis_rotation: torch.Tensor
    root_horizontal: torch.Tensor
    root_yaw: torch.Tensor
    drop: torch.Tensor
    remaining: torch.Tensor
    enabled: torch.Tensor
    requested_distance: torch.Tensor | None = None
    drop_requested_distance: torch.Tensor | None = None


def controls(raw, remaining, pelvis_world_height, floor=.30):
    if raw.shape[-1]!=ACTION_DIM or remaining.shape[-1]!=len(BANK_NAMES):
        raise ValueError('Wrong action/bank shape')
    specs=((0,2,2),(3,6,6),(7,10,10),(11,14,14),(15,17,17),(20,21,21))
    moves=[];left=[];requests=[]
    for i,(start,end,gate) in enumerate(specs):
        move,bank,distance=spend(raw[...,start:end],raw[...,gate:gate+1],remaining[...,i:i+1],return_request=True)
        moves.append(move);left.append(bank);requests.append(distance)
    drop_available=(pelvis_world_height-floor).clamp_min(0.)
    drop_requested=raw[...,18:19].clamp_min(0.)*raw[...,19:20].clamp(0.,1.)
    drop=torch.minimum(drop_requested,drop_available)
    # An exhausted channel cannot trigger even a zero-distance re-solve.
    # Positive gates with available capacity still retain action gradients at
    # exactly zero displacement, including the independent pelvis-drop channel.
    enabled=((raw[...,2]>0)&(remaining[...,0]>0))|((raw[...,6]>0)&(remaining[...,1]>0))|\
        ((raw[...,10]>0)&(remaining[...,2]>0))|((raw[...,14]>0)&(remaining[...,3]>0))|\
        ((raw[...,19]>0)&(drop_available[...,0]>0))
    return Controls(*moves,drop,torch.cat(left,-1),enabled,torch.cat(requests,-1),drop_requested)


def normalized_bank_cost_requests(action,limits):
    """Six original channels, plus equal-cost drop in the pelvis channel.

    Keep the original divisor of six: other penalties must not get diluted.
    Drop is independent of horizontal availability; a disabled horizontal bank
    uses the normal30cm scale, rather than disabling the drop's penalty too.
    This is loss bookkeeping only, with no change to actual bank spending.
    """
    requests=torch.where(limits>0,action.requested_distance/limits.clamp_min(1e-8),0.)
    horizontal=limits[...,:1]
    drop_scale=torch.where(horizontal>0,horizontal,DEFAULT_LIMITS[0])
    return torch.cat((requests[...,:1]+action.drop_requested_distance/drop_scale,requests[...,1:]),-1)


def horizontal_world(vector, root_axes):
    # Native root rows 0/1 span the ground; row 2 is world-up.
    local=torch.cat((vector,torch.zeros_like(vector[...,:1])),-1)
    return (local.unsqueeze(-2)@root_axes).squeeze(-2)


def yaw_rotation(angle):
    c,s=angle.cos(),angle.sin();z=torch.zeros_like(c);o=torch.ones_like(c)
    return torch.stack((c,z,-s,z,o,z,s,z,c),-1).reshape(*angle.shape,3,3)


def root_command_delta(initial_delta_world, yaw_offset):
    """Persistent yaw turns the command path, not just the facing direction."""
    if yaw_offset is None:return initial_delta_world
    return (initial_delta_world.unsqueeze(-2)@yaw_rotation(yaw_offset.squeeze(-1))).squeeze(-2)


def next_root(point, axes, initial_delta_world, initial_yaw, horizontal_shift,
              root_yaw_shift=None, root_yaw_offset=None):
    offset=root_yaw_offset
    turn=initial_yaw
    if root_yaw_shift is not None:
        offset=root_yaw_shift if offset is None else offset+root_yaw_shift
        turn=turn+root_yaw_shift
    delta=root_command_delta(initial_delta_world,offset)
    return point+delta+horizontal_world(horizontal_shift,axes), axes@yaw_rotation(turn.squeeze(-1))


def root_window(previous_point, previous_axes, current_point, current_axes,
                initial_delta_world, initial_yaw, steps, speed_scale, turn_scale, root_yaw_offset=None):
    """Full accepted-lower window; extrapolation only, independent of clip end.

    A shift is already included in current_point. It therefore displaces every
    future root equally, while the observed previous→current command correctly
    includes the shift's onset. No accumulating O(T) correction list is needed.
    """
    from transition_agents import native
    tl=native.tl
    prev_yaw=tl.heading_yaw_from_root(previous_axes)
    cur_yaw=tl.heading_yaw_from_root(current_axes)
    previous_heading=tl.yaw_to_row_matrix(prev_yaw)
    current_heading=tl.yaw_to_row_matrix(cur_yaw)
    delta=((current_point-previous_point).unsqueeze(-2)@previous_heading).squeeze(-2)
    history=torch.stack((delta[...,0]/speed_scale,delta[...,2]/speed_scale,
        tl.wrap_angle(cur_yaw-prev_yaw)/turn_scale),-1)
    offsets=torch.arange(1,steps+1,dtype=current_point.dtype,device=current_point.device)
    command=root_command_delta(initial_delta_world,root_yaw_offset)
    future=current_point[:,None]+offsets[None,:,None]*command[:,None]
    local=((future-current_point[:,None]).unsqueeze(-2)@current_heading[:,None]).squeeze(-2)
    yaw=offsets[None,:]*initial_yaw
    scale=offsets[None,:]*speed_scale
    feature=torch.stack(((local[...,0]/scale).clamp(-2,2),(local[...,2]/scale).clamp(-2,2),
        yaw.cos(),yaw.sin()),-1).flatten(-2)
    return torch.cat((history,feature),-1),future
