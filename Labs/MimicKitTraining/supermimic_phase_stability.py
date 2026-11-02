"""Freeze only the perturbed rows' feedback predictor in a disposable learner.

The predictor still reads the current pose and previous predicted phase each
tick. This does not replace autoregression with an authored clock. Normal phase
supervision, motor learning, rewards and termination rules remain unchanged.
"""
import copy
import torch
from torch import nn


class PhasePredictor(nn.Module):
    def __init__(self, model):
        super().__init__()
        self.layers=copy.deepcopy(model._actor_layers)
        self.output=copy.deepcopy(model._phase_out)
        self.unit=model._unit_phase
        self.eval()
        for p in self.parameters():p.requires_grad_(False)

    def forward(self, obs):
        value=self.output(self.layers(obs))
        return torch.nn.functional.normalize(value,dim=-1,eps=1e-6) if self.unit else value


def phase_cycles_difference(a,b):
    angle=torch.atan2(a[:,1],a[:,0])-torch.atan2(b[:,1],b[:,0])
    return torch.atan2(angle.sin(),angle.cos())/(2*torch.pi)


def install(agent,freeze_perturbed=False):
    predictor=PhasePredictor(agent._model)
    initial=[p.detach().clone() for p in predictor.parameters()]
    original=agent._decide_action
    reference=None
    reference_mask=None

    def decide(obs,info):
        nonlocal reference,reference_mask
        action,action_info=original(obs,info)
        env=agent._env
        if getattr(env,'_recovery_ready',False):
            ids=getattr(env,'_phase_feedback_ids',env._recovery_ids)
            mask=env._perturbed_rows[ids]
            with torch.no_grad():
                if reference is None:
                    reference=agent._obs_norm.normalize(obs[ids]).clone()
                    reference_mask=mask.clone()
                    torch.testing.assert_close(predictor(reference),agent._model.eval_phase(reference),atol=1e-6,rtol=1e-6)
                if freeze_perturbed:
                    frozen=predictor(agent._obs_norm.normalize(obs[ids]))
                    # Upstream queued the live prediction. Preserve normal rows
                    # exactly, including its zero-vector fallback semantics.
                    pending=env._pending_phase[ids].clone()
                    env.queue_phase_prediction(frozen)
                    env._pending_phase[ids[~mask]]=pending[~mask]
        return action,action_info

    def metrics():
        assert reference is not None,'No actual feedback observations captured'
        with torch.no_grad():
            original_phase=predictor(reference)
            live=agent._model.eval_phase(reference)
            drift=phase_cycles_difference(live,original_phase)[reference_mask]
            frozen_delta=torch.stack([(p-q).square().sum() for p,q in zip(predictor.parameters(),initial)]).sum().sqrt()
            assert float(frozen_delta)==0.,'Frozen predictor changed'
            return dict(live_drift_rms_cycles=float(drift.square().mean().sqrt()),
                        live_drift_p95_cycles=float(torch.quantile(drift.abs(),.95)),
                        live_drift_max_cycles=float(drift.abs().max()),
                        deployed_fixed_probe_drift_rms_cycles=0. if freeze_perturbed else float(drift.square().mean().sqrt()),
                        predictor_parameter_delta_l2=float(frozen_delta))

    agent._decide_action=decide
    # Deliberately return this object rather than registering it inside agent:
    # original learner state/optimizer layouts must stay intact.
    return predictor,metrics
