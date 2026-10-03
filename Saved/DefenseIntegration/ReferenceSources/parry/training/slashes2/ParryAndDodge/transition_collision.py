"""Collision objectives for the new joint-prior defense training.

This module does not alter the old checkpoint's objective. Inputs are complete
one-attack trajectories; padding is explicitly masked. Hard CCD selection is
detached, while distance/gap evaluated at the selected event is differentiable.
"""
from dataclasses import dataclass, field
import torch
from collision_objective import (
    conservative_first_contact, interpolate_obb, sat_gap, obb_feature_distance,
    CCD_GAP_EPSILON_M, CCD_TIME_TOLERANCE, DD_CONTACT_TEMPERATURE_M,
)
from defense_labels import collision_masks


def label_masks(raw_kinds, names, device):
    """Build once outside capture; anatomical hand_r must not alias the blade."""
    rows = [collision_masks(int(kind), names) for kind in raw_kinds]
    for kind, (_, blocking, _) in zip(raw_kinds, rows):
        if int(kind) >= 16 and not any(blocking):
            raise ValueError(f'No blocking collider for label {kind}')
    return tuple(torch.tensor([row[i] for row in rows], dtype=torch.bool,
                              device=device) for i in range(3))


@dataclass
class ContactOrder:
    protected: torch.Tensor
    harmful_hit: torch.Tensor
    harmful_interval: torch.Tensor
    harmful_collider: torch.Tensor
    harmful_fraction: torch.Tensor
    first_block_time: torch.Tensor
    first_harm_time: torch.Tensor
    pair_hits: torch.Tensor | None = field(default=None,init=False)
    interval_loss: torch.Tensor | None = field(default=None,init=False)


@torch.no_grad()
def contact_order(pair_hit, pair_time, blocking, harmful, valid):
    """Vectorized persistent first-contact ownership for B,T,C pair events.

    A strictly earlier block protects the entire remaining attack, including
    later intervals. Equal-time harmful+blocking contact is harmful, independent
    of collider order. Invalid/padded intervals cannot create protection/hits.
    """
    batch, intervals, colliders = pair_hit.shape
    ordinal = torch.arange(intervals, device=pair_time.device)[None, :, None]
    events = torch.where(pair_hit & valid[..., None], ordinal + pair_time, torch.inf)
    block_time = torch.where(blocking[:, None], events, torch.inf).flatten(1).amin(1)
    harms = torch.where(harmful[:, None], events, torch.inf).flatten(1)
    harm_time, flat_index = harms.min(1)
    protected = torch.isfinite(block_time) & (block_time < harm_time)
    interval = torch.div(flat_index, colliders, rounding_mode='floor')
    collider = flat_index.remainder(colliders)
    fraction = pair_time.flatten(1).gather(1, flat_index[:, None]).squeeze(1)
    # Inert finite values avoid inf arithmetic in the differentiable event path.
    fraction = torch.where(torch.isfinite(harm_time), fraction, 0.0)
    return ContactOrder(protected, torch.isfinite(harm_time) & ~protected,
                        interval, collider, fraction, block_time, harm_time)


@torch.no_grad()
def pair_contacts(dc0, da0, dc1, da1, dh, do, ac0, aa0, ac1, aa1, ah, ao):
    """One existing CCD kernel call for all pairs, never one call per bone."""
    batch, count = dc0.shape[:2]
    dr = torch.linalg.vector_norm(dh, dim=-1)
    ar = torch.linalg.vector_norm(ah, dim=-1)
    if dc0.is_cuda:
        from triton_ccd import first_contact_pairs
        hit, time, _, _ = first_contact_pairs(
            *(x.contiguous() for x in (dc0, da0, dc1, da1, dh, dr, do,
                                      ac0, aa0, ac1, aa1, ah, ar, ao)),
            tolerance=CCD_TIME_TOLERANCE, gap_epsilon=CCD_GAP_EPSILON_M,
            max_iterations=4096)
        return hit, time
    # CPU test oracle: a one-collider row retains every pair result from the
    # established conservative solver instead of discarding all but its minimum.
    def bodies(value): return value.reshape(batch * count, 1, *value.shape[2:])
    def attack(value):
        return value[:, None].expand(batch, count, *value.shape[1:]).reshape(
            batch * count, *value.shape[1:])
    first = conservative_first_contact(
        bodies(dc0), bodies(da0), bodies(dc1), bodies(da1), bodies(dh), bodies(dr),
        attack(ac0), attack(aa0), attack(ac1), attack(aa1), attack(ah), attack(ar),
        defender_center_offset_local=bodies(do), attacker_center_offset_local=attack(ao))
    hit, time = first.hit.reshape(batch, count), first.time.reshape(batch, count)
    # The old CPU oracle skips exact end-point touches; CUDA tests its endpoint.
    end_hit = sat_gap(dc1, da1, dh, ac1[:, None], aa1[:, None], ah[:, None]) <= CCD_GAP_EPSILON_M
    return hit | end_hit, torch.where(~hit & end_hit, 1.0, time)


def harmful_contact_loss(centers, axes, attack_centers, attack_axes, attack_half,
                         geometry, blocking, harmful, valid, *, all_contacts=False):
    """Same first-harmful-event DD surrogate, with Parry first-block protection.

    Shapes: centers B,F,C,3; axes B,F,C,3,3; valid B,F-1;
    masks B,C. Geometry names/masks must already remove absent swords.
    Returns one unweighted scalar per motion and detached event diagnostics.
    """
    batch, frames, count = centers.shape[:3]
    intervals = frames - 1
    def flatten(x): return x.reshape(batch * intervals, *x.shape[2:])
    half = geometry.half_sizes_m[None, None].expand(batch, intervals, count, 3)
    offset = geometry.center_offsets_local[None, None].expand_as(half)
    ah = attack_half[:, None].expand(batch, intervals, 3)
    ao = torch.zeros_like(attack_centers[:, :-1])
    hit, time = pair_contacts(
        flatten(centers[:, :-1]), flatten(axes[:, :-1]),
        flatten(centers[:, 1:]), flatten(axes[:, 1:]), flatten(half), flatten(offset),
        flatten(attack_centers[:, :-1]), flatten(attack_axes[:, :-1]),
        flatten(attack_centers[:, 1:]), flatten(attack_axes[:, 1:]), flatten(ah), flatten(ao))
    order = contact_order(hit.reshape(batch, intervals, count),
                          time.reshape(batch, intervals, count), blocking, harmful, valid)
    if all_contacts:
        # Dodge only: every harmful pair in every valid interval contributes.
        # Preserve first-contact diagnostics, but never let that selection hide
        # subsequent contacts or their gradients. Parry protection is unchanged.
        pair_hit=hit.reshape(batch,intervals,count) & valid[...,None] & harmful[:,None]
        fraction=torch.where(pair_hit,time.reshape(batch,intervals,count),0.).detach()
        dc,da=interpolate_obb(centers[:,:-1],axes[:,:-1],centers[:,1:],axes[:,1:],fraction,offset)
        def expand_attack(x):return x[:,:,None].expand(batch,intervals,count,*x.shape[2:])
        ac,aa=interpolate_obb(expand_attack(attack_centers[:,:-1]),expand_attack(attack_axes[:,:-1]),
            expand_attack(attack_centers[:,1:]),expand_attack(attack_axes[:,1:]),fraction)
        gap=sat_gap(dc,da,half,ac,aa,ah[:,:,None])
        penalties=torch.nn.functional.softplus(-gap/DD_CONTACT_TEMPERATURE_M)*DD_CONTACT_TEMPERATURE_M
        frames=torch.where(pair_hit,penalties,0.).sum(-1)
        order.pair_hits=pair_hit;order.interval_loss=frames
        return frames.sum(-1),order
    row = torch.arange(batch, device=centers.device)
    frame, bone, fraction = order.harmful_interval, order.harmful_collider, order.harmful_fraction
    dc, da = interpolate_obb(centers[row, frame, bone], axes[row, frame, bone],
                            centers[row, frame + 1, bone], axes[row, frame + 1, bone],
                            fraction, geometry.center_offsets_local[bone])
    ac, aa = interpolate_obb(attack_centers[row, frame], attack_axes[row, frame],
                            attack_centers[row, frame + 1], attack_axes[row, frame + 1], fraction)
    gap = sat_gap(dc, da, geometry.half_sizes_m[bone], ac, aa, attack_half)
    temperature = DD_CONTACT_TEMPERATURE_M
    loss = torch.nn.functional.softplus(-gap / temperature) * temperature
    return torch.where(order.harmful_hit, loss, 0.0), order


def required_block_contact(centers, axes, attack_centers, attack_axes, attack_half,
                           geometry, blocking, times, block_time):
    """Any designated-chain OBB must overlap at the recorded (fractional) time.

    Block time is supervision ONLY, never a predictor/agent feature. Caller
    validates that this event lies inside the real, unpadded trajectory.
    """
    batch, frames, count = centers.shape[:3]
    row = torch.arange(batch, device=centers.device)
    # searchsorted supports a different recorded timestamp for each motion.
    slot = torch.searchsorted(times.contiguous(), block_time[:, None].contiguous(), right=False)
    slot = (slot.squeeze(1) - 1).clamp(0, frames - 2)
    span = (times[row, slot + 1] - times[row, slot]).clamp_min(1e-8)
    fraction = ((block_time - times[row, slot]) / span).to(centers.dtype)
    dc, da = interpolate_obb(centers[row, slot], axes[row, slot],
                            centers[row, slot + 1], axes[row, slot + 1],
                            fraction[:, None], geometry.center_offsets_local[None])
    ac, aa = interpolate_obb(attack_centers[row, slot], attack_axes[row, slot],
                            attack_centers[row, slot + 1], attack_axes[row, slot + 1], fraction)
    distance = obb_feature_distance(dc, da, geometry.half_sizes_m[None],
                                   ac[:, None], aa[:, None], attack_half[:, None])
    return torch.where(blocking, distance, torch.inf).amin(1)


def self_harm_loss(centers,axes,geometry,present,valid,*,include_right_forearm=True,blade_body_indices=None):
    """Existing blade-vs-body + right-forearm-vs-torso objective per interval.

    A swordless row cannot select its blade in ANY pair. Blocking protection
    applies to the external attack only and never disables this self-harm term.
    This returns raw B,T penalties; apply the established PP/DD multiplier once.
    """
    batch,frames=centers.shape[:2];intervals=frames-1
    def flatten(x):return x.reshape(batch*intervals,*x.shape[2:])
    result=centers.new_zeros((batch,intervals))
    body_indices=geometry.self_body_indices if blade_body_indices is None else blade_body_indices
    for attacker,body in ((geometry.names.index('blade'),body_indices),
                          (geometry.names.index('lowerarm_r'),geometry.self_torso_indices)):
        if not include_right_forearm and attacker==geometry.names.index('lowerarm_r'):continue
        count=body.numel()
        c=centers.index_select(2,body);a=axes.index_select(2,body)
        h=geometry.half_sizes_m.index_select(0,body)[None,None].expand(batch,intervals,count,3)
        off=geometry.center_offsets_local.index_select(0,body)[None,None].expand_as(h)
        ac=centers[:,:,attacker];aa=axes[:,:,attacker]
        ah=geometry.half_sizes_m[attacker][None,None].expand(batch,intervals,3)
        ao=geometry.center_offsets_local[attacker][None,None].expand_as(ah)
        hits,times=pair_contacts(flatten(c[:,:-1]),flatten(a[:,:-1]),flatten(c[:,1:]),flatten(a[:,1:]),
            flatten(h),flatten(off),flatten(ac[:,:-1]),flatten(aa[:,:-1]),flatten(ac[:,1:]),flatten(aa[:,1:]),flatten(ah),flatten(ao))
        eligible=present[:,attacker,None,None] & present[:,None,body] & valid[:,:,None]
        hit=hits.reshape(batch,intervals,count) & eligible
        times=times.reshape(batch,intervals,count)
        first,index=torch.where(hit,times,torch.inf).min(-1)
        any_hit=torch.isfinite(first)
        fraction=torch.where(any_hit,first,0.).detach()
        row=torch.arange(batch,device=centers.device)[:,None]
        frame=torch.arange(intervals,device=centers.device)[None,:]
        dc,da=interpolate_obb(c[row,frame,index],a[row,frame,index],c[row,frame+1,index],a[row,frame+1,index],fraction,off[row,frame,index])
        atk,rotation=interpolate_obb(ac[:,:-1],aa[:,:-1],ac[:,1:],aa[:,1:],fraction,ao)
        gap=sat_gap(dc,da,h[row,frame,index],atk,rotation,ah)
        penalty=torch.nn.functional.softplus(-gap/.01)*.01
        result=result+torch.where(any_hit,penalty,0.)
    return result
