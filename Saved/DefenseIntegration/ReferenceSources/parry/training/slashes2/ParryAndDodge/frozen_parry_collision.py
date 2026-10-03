"""Experiment-only free-time, blocker-first collision objective.

Hard CCD decides success and row termination. Its event selection is detached;
the miss objective is a differentiable, sampled closest-feature surrogate, NOT
an exact continuous optimizer. No authored contact/hit timestamp is consumed.

For distances d at eligible blocker/time candidates, the attraction is
    -temperature * log(mean(exp(-d / temperature))).
The log-domain reduction retains useful gradients even for metre-scale misses.
Candidates after the first harmful event are excluded, and a witness just
before that event is added. Existing harmful-contact softplus is unchanged.
"""
from dataclasses import dataclass
from functools import lru_cache
import math
import torch

from collision_objective import (
    CCD_GAP_EPSILON_M, CCD_TIME_TOLERANCE, DD_CONTACT_TEMPERATURE_M,
    conservative_first_contact, interpolate_obb, obb_feature_distance, sat_gap,
)
from transition_collision import ContactOrder


CONTRACT = 'frozen_lower_free_time_confirmed_blocker_first_v1'
UPPER_BLOCKERS = ('blade', 'upperarm_l', 'lowerarm_l', 'hand_l',
                  'upperarm_r', 'lowerarm_r', 'hand_r')


@lru_cache(maxsize=32)
def _blocker_indices(names, count, device):
    # Populated during the graph runner's normal warmup. Never perform a fresh
    # CPU->CUDA index upload inside a captured training replay.
    ids = ([i for i, name in enumerate(names) if name in UPPER_BLOCKERS]
           if names is not None else list(range(count)))
    if not ids:
        raise ValueError('The frozen-lower experiment requires an upper-body blocker')
    return torch.tensor(ids, device=device)


@dataclass(frozen=True)
class FreeTimingConfig:
    lattice_samples: int = 3
    temperature_m: float = .02
    # Expressed in input time units (the training pack uses authored frames).
    tie_tolerance: float = 2. * CCD_TIME_TOLERANCE
    max_iterations: int = 4096
    cpu_max_iterations: int = 96

    def __post_init__(self):
        if self.lattice_samples < 2:
            raise ValueError('At least both interval endpoints must be sampled')
        if not math.isfinite(self.temperature_m) or self.temperature_m <= 0:
            raise ValueError('Positive finite distance temperature required')
        if not math.isfinite(self.tie_tolerance) or self.tie_tolerance < 0:
            raise ValueError('Nonnegative finite tie tolerance required')
        if self.max_iterations < 2 or self.cpu_max_iterations < 2:
            raise ValueError('CCD iteration budget must be at least two')


@dataclass
class PairEvents:
    confirmed: torch.Tensor
    possible: torch.Tensor
    time: torch.Tensor
    iterations: torch.Tensor
    resolved: torch.Tensor
    actual_gap: torch.Tensor


@dataclass
class FreeContactOrder(ContactOrder):
    block_interval: torch.Tensor
    block_collider: torch.Tensor
    block_fraction: torch.Tensor
    unresolved_pairs: torch.Tensor

    @property
    def success(self):
        return self.protected


@torch.no_grad()
def confirmed_pair_contacts(dc0, da0, dc1, da1, dh, do,
                            ac0, aa0, ac1, aa1, ah, ao, config=FreeTimingConfig()):
    """One batched strict CCD call, retaining conservative-fallback metadata.

    The legacy kernel accepts a speed-scaled near miss. For this experiment its
    time tolerance is zero, so advancement continues until an actual SAT touch
    (within the existing metre epsilon), escape, or iteration exhaustion. The
    The strict kernel's own SAT gap certifies CUDA contact. Recomputing that
    boundary with PyTorch has different float32 rounding and must not veto it.
    The independent gap is retained for diagnostics. Unresolved searches can
    conservatively count as harmful but can NEVER grant blocker protection.
    """
    batch, count = dc0.shape[:2]
    dr = torch.linalg.vector_norm(dh, dim=-1)
    ar = torch.linalg.vector_norm(ah, dim=-1)
    if dc0.is_cuda:
        from triton_ccd import first_contact_pairs
        budget = config.max_iterations
        possible, fraction, kernel_gap, iterations = first_contact_pairs(
            *(x.contiguous() for x in (dc0, da0, dc1, da1, dh, dr, do,
                                      ac0, aa0, ac1, aa1, ah, ar, ao)),
            tolerance=0., gap_epsilon=CCD_GAP_EPSILON_M,
            max_iterations=budget)
    else:
        budget = config.cpu_max_iterations
        def bodies(value):
            return value.reshape(batch * count, 1, *value.shape[2:])
        def attack(value):
            return value[:, None].expand(batch, count, *value.shape[1:]).reshape(
                batch * count, *value.shape[1:])
        event = conservative_first_contact(
            bodies(dc0), bodies(da0), bodies(dc1), bodies(da1), bodies(dh), bodies(dr),
            attack(ac0), attack(aa0), attack(ac1), attack(aa1), attack(ah), attack(ar),
            defender_center_offset_local=bodies(do),
            attacker_center_offset_local=attack(ao), tolerance=0., maximum_advances=budget)
        possible = event.hit.reshape(batch, count)
        fraction = event.time.reshape(batch, count)
        iterations = event.iterations.reshape(batch, count)
        # The existing CPU oracle escapes before checking an exact endpoint.
        endpoint = (sat_gap(dc1, da1, dh, ac1[:, None], aa1[:, None], ah[:, None])
                    <= CCD_GAP_EPSILON_M)
        endpoint = endpoint & ~possible & (iterations < budget)
        possible = possible | endpoint
        fraction = torch.where(endpoint, 1., fraction)
    resolved = iterations < budget
    safe_fraction = torch.where(possible & torch.isfinite(fraction), fraction, 0.)
    dc, da = interpolate_obb(dc0, da0, dc1, da1, safe_fraction, do)
    ac, aa = interpolate_obb(ac0[:, None], aa0[:, None], ac1[:, None], aa1[:, None],
                            safe_fraction, ao[:, None])
    actual_gap = sat_gap(dc, da, dh, ac, aa, ah[:, None])
    # Use the gap from the same arithmetic that selected the event time. This
    # does not widen CCD's spatial/time tolerance or accept exhausted searches.
    certificate_gap = kernel_gap if dc0.is_cuda else actual_gap
    confirmed = strict_contact_certificate(possible, resolved, certificate_gap, actual_gap)
    return PairEvents(confirmed, possible, safe_fraction, iterations, resolved, actual_gap)


def strict_contact_certificate(possible, resolved, certificate_gap, diagnostic_gap):
    return (possible & resolved & torch.isfinite(certificate_gap)
            & torch.isfinite(diagnostic_gap) & (certificate_gap <= CCD_GAP_EPSILON_M))


@torch.no_grad()
def first_contact_order(pairs, blocking, harmful, valid, times,
                        config=FreeTimingConfig()):
    """Only confirmed earlier blocks protect; unresolved harmful events do not."""
    batch, intervals, count = pairs.possible.shape
    event_time = times[:, :-1, None] + pairs.time * (times[:, 1:] - times[:, :-1])[:, :, None]
    block_events = torch.where(pairs.confirmed & valid[..., None] & blocking[:, None],
                               event_time, torch.inf)
    harm_events = torch.where(pairs.possible & valid[..., None] & harmful[:, None],
                              event_time, torch.inf)
    block_time, block_index = block_events.flatten(1).min(1)
    harm_time, harm_index = harm_events.flatten(1).min(1)
    # The tolerance prevents numerical collider order from making a tie a win.
    protected = torch.isfinite(block_time) & (block_time + config.tie_tolerance < harm_time)
    harm_hit = torch.isfinite(harm_time) & ~protected
    fractions = pairs.time.flatten(1)
    harm_fraction = fractions.gather(1, harm_index[:, None]).squeeze(1)
    block_fraction = fractions.gather(1, block_index[:, None]).squeeze(1)
    return FreeContactOrder(
        protected, harm_hit, harm_index // count, harm_index % count,
        torch.where(torch.isfinite(harm_time), harm_fraction, 0.), block_time, harm_time,
        block_index // count, block_index % count,
        torch.where(torch.isfinite(block_time), block_fraction, 0.),
        ((~pairs.resolved) & valid[..., None] & (blocking | harmful)[:, None]).sum((1, 2)))


def blocker_attraction(centers, axes, attack_centers, attack_axes, attack_half,
                       geometry, blocking, valid, times, pairs, order,
                       config=FreeTimingConfig()):
    """Finite sampled free-time loss; exact CCD witnesses augment the lattice.

    Only potential upper-body blocking colliders incur closest-feature work.
    Their per-row mask still determines eligibility. Candidate-time selection
    is detached; gradients flow through interpolated controlled transforms.
    """
    batch, frames, count = centers.shape[:3]
    intervals = frames - 1
    names = getattr(geometry, 'names', None)
    index = _blocker_indices(None if names is None else tuple(names), count, centers.device)
    c = centers.index_select(2, index)
    a = axes.index_select(2, index)
    half = geometry.half_sizes_m.index_select(0, index)
    offset = geometry.center_offsets_local.index_select(0, index)
    selected_blocking = blocking.index_select(1, index)
    with torch.no_grad():
        lattice = torch.linspace(0., 1., config.lattice_samples, device=centers.device,
                                 dtype=centers.dtype)[None, None].expand(batch, intervals, -1)
        blocker_event = torch.where(pairs.confirmed & blocking[:, None], pairs.time, torch.inf).amin(-1)
        blocker_event = torch.where(torch.isfinite(blocker_event), blocker_event, .5)
        span = (times[:, 1:] - times[:, :-1]).clamp_min(1e-8)
        # A candidate before the harmful witness, not at a tied contact.
        pre_harm_time = torch.where(torch.isfinite(order.first_harm_time),
                                    order.first_harm_time - 2. * config.tie_tolerance,
                                    times[:, -1])
        pre_harm = ((pre_harm_time[:, None] - times[:, :-1]) / span).clamp(0., 1.)
        fraction = torch.cat((lattice, blocker_event[..., None], pre_harm[..., None]), -1)
        sample_time = times[:, :-1, None] + fraction * span[..., None]
        eligible = valid[..., None] & (sample_time + config.tie_tolerance < order.first_harm_time[:, None, None])
        # At an initial overlap there is no feasible earlier time. Keep a finite
        # attraction at the first valid start; CCD still judges the row failed.
        missing = ~eligible.flatten(1).any(1)
        first = valid.to(torch.int64).argmax(1)
        fallback = ((torch.arange(intervals, device=centers.device)[None, :, None] == first[:, None, None])
                    & (torch.arange(fraction.shape[2], device=centers.device)[None, None, :] == 0))
        eligible = eligible | (missing[:, None, None] & fallback & valid[..., None])
        eligible = eligible[..., None] & selected_blocking[:, None, None]
    dc, da = interpolate_obb(c[:, :-1, None], a[:, :-1, None], c[:, 1:, None], a[:, 1:, None],
                            fraction[..., None], offset[None, None, None])
    ac, aa = interpolate_obb(attack_centers[:, :-1, None], attack_axes[:, :-1, None],
                            attack_centers[:, 1:, None], attack_axes[:, 1:, None], fraction)
    distance = obb_feature_distance(dc, da, half[None, None, None],
                                    ac[..., None, :], aa[..., None, :, :], attack_half[:, None, None, None])
    logits = torch.where(eligible, -distance / config.temperature_m, -1e6)
    number = eligible.flatten(1).sum(1).clamp_min(1).to(distance.dtype)
    loss = config.temperature_m * (number.log() - torch.logsumexp(logits.flatten(1), 1))
    active = valid.any(1) & selected_blocking.any(1) & ~order.protected
    return torch.where(active, loss.clamp_min(0.), 0.)


def free_contact_objective(centers, axes, attack_centers, attack_axes, attack_half,
                           geometry, blocking, harmful, valid, times=None,
                           config=FreeTimingConfig(), block_time=None):
    """Score B,F,C trajectories; valid is B,F-1 and times (optional) is B,F.

    terminal_frame is an index in these input poses, NOT an authored timestamp.
    interval_valid includes the successful contact interval, excludes all later
    intervals, and is unchanged on failures. Every tensor has a static shape.
    Row replacement belongs to the caller; this module never changes the bank.
    """
    batch, frames, count = centers.shape[:3]
    intervals = frames - 1
    if intervals < 1 or valid.shape != (batch, intervals):
        raise ValueError('Need one validity flag per real transition')
    if times is None:
        times = torch.arange(frames, device=centers.device, dtype=centers.dtype)[None].expand(batch, -1)
    if times.shape != (batch, frames):
        raise ValueError('Need one timestamp per input pose')
    def flat(value):
        return value.reshape(batch * intervals, *value.shape[2:])
    half = geometry.half_sizes_m[None, None].expand(batch, intervals, count, 3)
    offset = geometry.center_offsets_local[None, None].expand_as(half)
    ah = attack_half[:, None].expand(batch, intervals, 3)
    ao = torch.zeros_like(attack_centers[:, :-1])
    pairs = confirmed_pair_contacts(
        flat(centers[:, :-1]), flat(axes[:, :-1]), flat(centers[:, 1:]), flat(axes[:, 1:]),
        flat(half), flat(offset), flat(attack_centers[:, :-1]), flat(attack_axes[:, :-1]),
        flat(attack_centers[:, 1:]), flat(attack_axes[:, 1:]), flat(ah), flat(ao), config)
    pairs = PairEvents(*(getattr(pairs, name).reshape(batch, intervals, count)
                         for name in PairEvents.__dataclass_fields__))
    order = first_contact_order(pairs, blocking, harmful, valid, times, config)
    row = torch.arange(batch, device=centers.device)
    frame, bone = order.harmful_interval, order.harmful_collider
    dc, da = interpolate_obb(centers[row, frame, bone], axes[row, frame, bone],
                            centers[row, frame + 1, bone], axes[row, frame + 1, bone],
                            order.harmful_fraction, geometry.center_offsets_local[bone])
    ac, aa = interpolate_obb(attack_centers[row, frame], attack_axes[row, frame],
                            attack_centers[row, frame + 1], attack_axes[row, frame + 1],
                            order.harmful_fraction)
    gap = sat_gap(dc, da, geometry.half_sizes_m[bone], ac, aa, attack_half)
    penalty = torch.nn.functional.softplus(-gap / DD_CONTACT_TEMPERATURE_M) * DD_CONTACT_TEMPERATURE_M
    ccd = torch.where(order.harmful_hit, penalty, 0.)
    selected_block_time = None
    if block_time is None:
        required = blocker_attraction(centers, axes, attack_centers, attack_axes, attack_half,
                                      geometry, blocking, valid, times, pairs, order, config)
    else:
        from frozen_parry_timed_block import timed_block_contact
        required, selected_block_time = timed_block_contact(centers, axes, attack_centers,
            attack_axes, attack_half, geometry, blocking, times, block_time)
    ordinal = torch.arange(intervals, device=centers.device)[None]
    interval_valid = valid & (~order.protected[:, None] | (ordinal <= order.block_interval[:, None]))
    last_frame = torch.where(valid, ordinal + 1, 0).amax(1)
    terminal_frame = torch.where(order.protected, order.block_interval + 1, last_frame)
    return dict(ccd=ccd, required_block=required, events=order,
                terminal_frame=terminal_frame, interval_valid=interval_valid, pairs=pairs,
                selected_block_time=selected_block_time)
