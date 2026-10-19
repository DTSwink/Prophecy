"""CPU regression: accepted learning, rejected Adam transaction and full audit."""
import sys
from pathlib import Path
from types import SimpleNamespace
import torch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Saved/MimicKitMotorAudit/source/MimicKit/mimickit'))
from learning.mp_optimizer import MPOptimizer
from learning.distribution_gaussian_diag import DistributionGaussianDiag
from kl_guard import Snapshot, guarded_actor_update
torch.set_num_threads(2)


class Model(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.weight=torch.nn.Parameter(torch.zeros(1))
    def eval_actor(self, obs):
        return DistributionGaussianDiag(obs*self.weight, torch.zeros_like(obs))


def make(lr, limit):
    model=Model(); opt=MPOptimizer(dict(type='Adam',learning_rate=lr),list(model.parameters()))
    obs=torch.ones(32,1)
    return SimpleNamespace(_actor_kl_limit=limit,_actor_kl_probe_size=16,_actor_min_lr=1e-7,
        _actor_optimizer=opt,_model=model,_obs_norm=SimpleNamespace(normalize=lambda x:x),
        _exp_buffer=SimpleNamespace(get_data_flat=lambda _:obs,sample=lambda n:{}),
        _compute_actor_loss=lambda b:dict(actor_loss=(model.weight-1).square().mean()))


def main():
    agent=make(.01,.02)
    result=guarded_actor_update(agent,16,5)
    assert result['actor_steps_accepted']==5 and agent._model.weight>0
    assert 0<result['policy_kl']<.02
    # Restore a populated Adam state after an unsafe proposal, not just weights.
    optimizer=agent._actor_optimizer
    optimizer._optimizer.param_groups[0]['lr']=10.
    prior=Snapshot(optimizer)
    result=guarded_actor_update(agent,16,5)
    assert result['actor_steps_accepted']==0 and result['actor_steps_rejected']==1
    assert torch.equal(agent._model.weight,prior.parameters[0])
    assert optimizer._steps==prior.steps
    state=optimizer._optimizer.state_dict()
    for key,values in prior.state['state'].items():
        for name,value in values.items():assert torch.equal(value,state['state'][key][name])
    assert optimizer._optimizer.param_groups[0]['lr']==5.
    assert result['policy_kl']==0
    # First update has no Adam state; rollback must remove newly created moments.
    fresh=make(10.,.02)
    result=guarded_actor_update(fresh,16,5)
    assert fresh._actor_optimizer._optimizer.state_dict()['state']=={}
    assert fresh._model.weight==0 and result['actor_steps_rejected']==1
    # Full-rollout check catches an unsafe subset which the cheap probe missed.
    other=make(.1,.02)
    obs=torch.cat((torch.ones(31,1),torch.tensor([[100.]])))
    other._exp_buffer.get_data_flat=lambda _:obs
    other._actor_kl_probe_size=1
    torch.manual_seed(7)
    result=guarded_actor_update(other,16,1)
    assert result['actor_full_rollback']==1 and other._model.weight==0
    assert other._actor_optimizer._optimizer.state_dict()['state']=={}
    print('PASS: learning accepted; first/stateful Adam updates rolled back exactly; full-rollout KL catches probe miss')


if __name__=='__main__':main()
