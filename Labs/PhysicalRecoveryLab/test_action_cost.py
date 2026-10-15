"""Adversarial saturation check: identical physical commands, unequal requests.

The raw cost and observed history must distinguish requests beyond the input
bound, while actual body actuation keeps the same safety bound.
"""
import json
import torch
import warp as wp
from recovery_env import RecoveryEnv,OUT


def main():
    torch.set_num_threads(1);torch.manual_seed(142);wp.init()
    env=RecoveryEnv(4,auto_reset=False,integrator='implicitfast',native_motors=True,relative_targets=True,
        action_rate_sum=True,reward_dt_scale=True,raw_action_cost=True,ccd_iterations=100,gyroscopic_forces=False)
    requests=torch.arange(5.,9.,device='cuda')[:,None].expand(-1,env.num_actions).clone()
    _,reward,_,_=env.step(requests)
    assert torch.equal(env.controller.actions,torch.full_like(requests,4.))
    assert torch.equal(env.previous_actions,requests)
    assert torch.equal(env.get_observations()['actor'][:,-env.num_actions:],requests)
    assert torch.equal(env.previous_cost_actions,requests)
    # Every world receives the exact same bounded command and starting pose.
    # Removing its independently calculated requested-action cost must expose
    # the same physical reward, within ordinary float reduction noise.
    uncensored_cost=.01*requests.square().sum(1)/30
    physical_reward=reward+uncensored_cost
    spread=float(physical_reward.max()-physical_reward.min());assert spread<1e-5,spread
    observed=float(reward[0]-reward[-1]);expected=float(uncensored_cost[-1]-uncensored_cost[0])
    assert abs(observed-expected)<1e-5,(observed,expected)
    env.step(requests+1)
    assert torch.equal(env.previous_cost_actions,requests+1)
    mask=torch.tensor([True,False,False,False],device='cuda');env.reset(mask)
    assert torch.equal(env.previous_cost_actions[0],torch.zeros(env.num_actions,device='cuda'))
    assert torch.equal(env.previous_cost_actions[1:],(requests+1)[1:])
    env.raw_action_cost=False;env.reset(torch.ones(4,device='cuda',dtype=torch.bool))
    _,legacy_reward,_,_=env.step(requests)
    assert float(legacy_reward.max()-legacy_reward.min())<1e-5
    assert torch.equal(env.previous_cost_actions,torch.full_like(requests,4.))
    result={'passed':True,'rig_sha256':env.metadata['rig_sha256'],'requests':[5,6,7,8],'applied_bound':4,
        'requested_cost_reward_difference_5_vs_8':observed,'independent_expected_difference':expected,
        'physical_reward_spread':spread,'requested_history_is_observed':True,'selective_reset_clears_cost_history':True,'legacy_mode_reproduces_old_clipped_cost':True}
    (OUT/'raw-action-cost-tests.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
