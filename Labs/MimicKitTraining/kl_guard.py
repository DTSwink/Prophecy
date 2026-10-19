"""Transactional actor updates, bounded by analytic Gaussian KL.

Probe each proposed step; verify the accepted result on the complete rollout.
Rejected updates restore weights AND optimizer moments/counters. No shutdown.
"""
import copy
import math
import torch
from util import torch_util


class Snapshot:
    def __init__(self, optimizer):
        self.wrapper = optimizer
        self.parameters = [p.detach().clone() for p in optimizer._param_list]
        self.state = copy.deepcopy(optimizer._optimizer.state_dict())
        self.steps = optimizer._steps

    @torch.no_grad()
    def restore(self):
        for parameter, saved in zip(self.wrapper._param_list, self.parameters):
            parameter.copy_(saved)
        self.wrapper._optimizer.load_state_dict(self.state)
        self.wrapper._steps = self.steps


def gaussian_kl(old_mean, old_logstd, current):
    # KL(old || new), summing action dimensions, then averaging states.
    delta = current.logstd-old_logstd
    return .5*(torch.expm1(-2*delta)+2*delta +
        ((old_mean-current.mean)/current.stddev).square()).sum(-1).mean()


def guarded_actor_update(agent, batch_size, num_steps):
    limit = agent._actor_kl_limit
    optimizer = agent._actor_optimizer
    initial = Snapshot(optimizer)
    obs = agent._obs_norm.normalize(agent._exp_buffer.get_data_flat('obs'))
    # Random subset, without consuming the experience buffer's sampling order.
    count = min(agent._actor_kl_probe_size, len(obs))
    indices = torch.randperm(len(obs), device=obs.device)[:count]
    probe = obs[indices]
    with torch.no_grad():
        old = agent._model.eval_actor(obs)
        old_mean, old_logstd = old.mean.detach().clone(), old.logstd.detach().clone()
    info = {}
    accepted = rejected = 0
    proposed_peak = 0.
    for _ in range(num_steps):
        batch = agent._exp_buffer.sample(batch_size)
        previous = Snapshot(optimizer)
        loss_info = agent._compute_actor_loss(batch)
        optimizer.step(loss_info['actor_loss'])
        with torch.no_grad():
            kl_value = gaussian_kl(old_mean[indices], old_logstd[indices], agent._model.eval_actor(probe))
            finite = torch.stack([p.isfinite().all() for p in optimizer._param_list]).all()
            kl = float(torch.where(finite, kl_value, kl_value.new_tensor(float('inf'))))
        proposed_peak = max(proposed_peak, kl) if math.isfinite(kl) else float('inf')
        if not math.isfinite(kl) or kl > limit:
            previous.restore()
            rejected += 1
            # A first-step rejection would otherwise repeat forever. Lower the
            # LR for the next fresh batch; preserve it in optimizer checkpoints.
            if accepted == 0:
                for group in optimizer._optimizer.param_groups:
                    group['lr'] = max(agent._actor_min_lr, group['lr']*.5)
            if not math.isfinite(kl):
                print('ACTOR WARNING: nonfinite proposal undone; Adam state restored; training continues', flush=True)
            break
        accepted += 1
        torch_util.add_torch_dict(loss_info, info)
    if accepted:
        torch_util.scale_torch_dict(1./accepted, info)
    else:
        # Report finite unchanged-policy metrics, not the rejected proposal.
        with torch.no_grad():
            info = agent._compute_actor_loss(batch)
    with torch.no_grad():
        full_kl = float(gaussian_kl(old_mean, old_logstd, agent._model.eval_actor(obs)))
    full_rollback = not math.isfinite(full_kl) or full_kl > limit
    if full_rollback:
        initial.restore()
        for group in optimizer._optimizer.param_groups:
            group['lr'] = max(agent._actor_min_lr, group['lr']*.5)
        rejected += accepted
        accepted = 0
        full_kl = 0.
    value = lambda v: torch.tensor(float(v), device=obs.device)
    info.update(policy_kl=value(full_kl), policy_kl_proposed=value(proposed_peak if math.isfinite(proposed_peak) else -1),
        actor_steps_accepted=value(accepted), actor_steps_rejected=value(rejected),
        actor_full_rollback=value(full_rollback), actor_learning_rate=value(optimizer._optimizer.param_groups[0]['lr']))
    return info
