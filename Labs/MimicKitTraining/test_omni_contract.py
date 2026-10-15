"""Local CPU contract checks. No optimizer steps, training or allocation."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'Saved/MimicKitUEFN/dependencies'),
             str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit')]
import json
import numpy as np
import torch
from gymnasium.spaces import Box
from unittest.mock import patch
from omni_policy import OmniPPOModel, circular_phase
from omni_walk import OmniWalkEnv, phase_at
from absolute_walk import AbsoluteWalkEnv


def run():
    torch.set_num_threads(1)
    # Test actual environment observation assembly without physics. Sentinel
    # physical state remains unchanged; exactly five floats are appended.
    env=object.__new__(OmniWalkEnv)
    env._motion_ids=torch.tensor([0,1,0])
    env._gaits=torch.tensor([0.,1.])
    env._directions=torch.tensor([[1.,0.],[0.,-1.]])
    env._phase_offsets=torch.tensor([.25,.6])
    times=torch.tensor([.99,.1,.999999]);duration=torch.tensor([1.,.6])
    class Lib:
        def get_motion_length(self,ids):return duration[ids]
    class Engine:
        def get_timestep(self):return 1/30
    env._motion_lib=Lib();env._engine=Engine()
    env._get_motion_times=lambda ids=None:times if ids is None else times[ids]
    physical=torch.arange(3*142,dtype=torch.float32).view(3,142)
    with patch.object(AbsoluteWalkEnv,'_compute_obs',lambda self,ids=None:physical if ids is None else physical[ids]):
        obs=env._compute_obs();subset=env._compute_obs(torch.tensor([2,0]))
    assert obs.shape==(3,147)
    torch.testing.assert_close(obs[:,:142],physical)
    torch.testing.assert_close(subset,obs[[2,0]])
    torch.testing.assert_close(obs[:,142],torch.tensor([0.,1.,0.]))
    torch.testing.assert_close(obs[:,143:145],torch.tensor([[1.,0.],[0.,-1.],[1.,0.]]))
    before=times.clone();target=env.next_phase_target()
    torch.testing.assert_close(times,before) # no clock feedback
    torch.testing.assert_close(target,circular_phase((times+1/30)/duration[env._motion_ids]+env._phase_offsets[env._motion_ids]),atol=1e-6,rtol=1e-5)
    torch.testing.assert_close(phase_at(torch.tensor([1.-1e-7]),torch.ones(1),torch.zeros(1)),
                               phase_at(torch.tensor([1.+1e-7]),torch.ones(1),torch.zeros(1)),atol=2e-6,rtol=0)
    class Spaces:
        def get_obs_space(self):return Box(-np.inf,np.inf,(147,))
        def get_action_space(self):return Box(-1.,1.,(34,))
    config=dict(actor_net='fc_1024_512_512',critic_net='fc_1024_512_512',
                actor_init_output_scale=.01,actor_std_type='FIXED',action_std=.05)
    model=OmniPPOModel(config,Spaces())
    for trunk in (model._actor_layers,model._critic_layers):
        assert [m.out_features for m in trunk if isinstance(m,torch.nn.Linear)]==[1024,512,512]
    x=torch.randn(3,147);pred=model.eval_phase(x)
    assert pred.shape==(3,2) and model.eval_critic(x).shape==(3,1)
    action=model.eval_actor(x).sample();assert action.shape==(3,34)
    actor_ids={id(p) for p in model.get_actor_params()}
    assert all(id(p) in actor_ids for p in model._phase_out.parameters())
    ((pred-target)**2).mean().backward()
    assert model._phase_out.weight.grad.abs().sum()>0
    assert model._actor_layers[0].weight.grad.abs().sum()>0
    assert all(p.grad is None for p in model._action_dist.parameters())
    assert all(p.grad is None for p in model._critic_layers.parameters())
    report=dict(passed=True,device='cpu',hidden_widths=[1024,512,512],command_floats=5,
                motor_outputs=34,phase_outputs=2,wrap_test=True,subset_test=True,
                phase_backprop=True,optimizer_steps=0,physics_test=False,
                note='142 physical inputs here are a test fixture, not a measured integrated observation count')
    (ROOT/'Saved/MimicKitUEFN/omni-contract-tests.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
if __name__=='__main__':run()
