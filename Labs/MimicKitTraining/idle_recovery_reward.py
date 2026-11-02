"""State-only bounded recovery reward for perturbed idle; no simulator side effects.

Inputs contain unweighted SI signals. The caller selects perturbed idle rows;
normal idle and locomotion keep their existing objective. Existing terminal
penalties must be subtracted AFTER this function. Do not multiply this reward by
the old COM2 gate: speed has its own independent bounded component here.
"""
import torch

COST_NAMES = (
    'idle_stop', 'idle_pose', 'idle_smooth', 'idle_steps', 'idle_slip',
    'idle_posture_guard',
)


def bounded_cost(value: torch.Tensor, scale: float) -> torch.Tensor:
    value = value.clamp_min(0.)
    return value / (scale + value)


def idle_recovery_reward(
    speed_sq: torch.Tensor,
    pose_cost: torch.Tensor,
    foot_reversal_raw: torch.Tensor,
    leg_reversal_raw: torch.Tensor,
    head_reversal_raw: torch.Tensor,
    cadence_raw: torch.Tensor,
    stance_slip_sq: torch.Tensor,
    head_height_ratio: torch.Tensor,
    pelvis_up_dot: torch.Tensor,
    lowest_foot_height: torch.Tensor = None,
):
    """Return (reward, component_costs), exact reward = 1 - sum(costs).

    Scalars are shape (...); reversal arrays are (..., 2): translation m²/s²,
    then rotation rad²/s². speed_sq is horizontal COM2 velocity error squared;
    pose_cost is the existing weighted pose/prior cost excluding COM2, all
    reversals, cadence and newly appended idle terms. cadence_raw is existing
    pre-handoff cadence cost. stance_slip_sq is mean squared XY material-contact
    point velocity of grounded feet (airborne feet contribute zero).

    pelvis_up_dot must compare the current pelvis to the authored idle pelvis:
    world-up component of rotate(q_current * inverse(q_idle), [0,0,1]). Thus
    arbitrary world yaw is free and neutral authored pelvis orientation is 1.
    head_height_ratio is current world head height / idle-reference head height.

    Speed's characteristic error is 0.5m/s, with 0.05m/s squared deadband.
    Smooth raw scales: opposing translation 0.2m/s, rotation 1rad/s; head0.1m/s.
    Step scale0.04 is squared20% cadence excess; slip characteristic0.2m/s.
    At high speed the style pressures remain25% active, approaching100% as the
    body settles. No elapsed-time input: the same physical state earns the same
    reward before or after a push. Speed improvement always wins against this
    increased style pressure: .55 > .75*(.15+.10+.10).
    """
    stop = bounded_cost((speed_sq-.05**2).clamp_min(0.), .5**2)
    settle = .25 + .75*(1.-stop)
    smooth = (
        bounded_cost(foot_reversal_raw[..., 0], .2**2)
        + bounded_cost(foot_reversal_raw[..., 1], 1.)
        + bounded_cost(leg_reversal_raw[..., 0], .2**2)
        + bounded_cost(leg_reversal_raw[..., 1], 1.)
        + bounded_cost(head_reversal_raw, .1**2)
    ) / 5.
    terms = torch.stack((
        .55*stop,
        .10*bounded_cost(pose_cost, 1.),
        .15*settle*smooth,
        .10*settle*bounded_cost(cadence_raw, .04),
        .10*settle*bounded_cost((stance_slip_sq-.02**2).clamp_min(0.), .2**2),
    ), -1)
    base_reward = (1.-terms.sum(-1)).clamp(0., 1.)
    # Dense safety guard; a stationary fallen body cannot collect the stop bonus.
    # Full credit above85% idle head height and within~37deg of authored up.
    height = ((head_height_ratio-.4)/.45).clamp(0., 1.)
    upright = ((pelvis_up_dot-.2)/.6).clamp(0., 1.)
    support = torch.ones_like(height) if lowest_foot_height is None else (1.-.75*((lowest_foot_height-.02)/.15).clamp(0.,1.))
    posture = height*upright*support
    guard = base_reward*(1.-posture)
    return base_reward*posture, torch.cat((terms, guard[..., None]), -1)
