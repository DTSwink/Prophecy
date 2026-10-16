"""Reject invalid PPO batches before optimization; never silently repair data."""
import torch


def invalid_batch(buffers):
    masks = {name: ~torch.isfinite(value).flatten(2).all(-1) if value.ndim>2 else ~torch.isfinite(value)
             for name,value in buffers.items() if value.is_floating_point()}
    if not masks: return None
    combined = torch.stack(list(masks.values())).any(0)
    if not bool(combined.any()): return None
    return {name: mask.nonzero().cpu().tolist()[:32] for name,mask in masks.items() if bool(mask.any())}


def install_guard(agent, report):
    original = agent._rollout_train
    def rollout(steps):
        original(steps)
        validator=getattr(agent._env._engine,'validate_transfer_solver',None)
        if validator:
            try:validator()
            except FloatingPointError as error:
                report(dict(reason='Physics solver rejected rollout BEFORE PPO optimization',error=str(error)))
                raise
        invalid = invalid_batch(agent._exp_buffer._buffers)
        if invalid:
            report(dict(reason='Invalid rollout rejected BEFORE PPO optimization; last verified checkpoint retained',
                        invalid_step_world_pairs=invalid))
            raise FloatingPointError('Invalid rollout; this trial stopped, other sweep trials unaffected')
    agent._rollout_train = rollout
