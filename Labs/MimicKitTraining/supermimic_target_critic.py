"""Isolated SHAC target-critic ablation; native reward and actor stay unchanged.

SHAC's alpha is the retained OLD target fraction: .4 target + .6 online.
This remains learned dynamics, not a reproduction of its differentiable simulator.
"""
import argparse
import copy
import json
from pathlib import Path

import torch


def make_target(model):
    target=copy.deepcopy(model).eval()
    for parameter in target.parameters():
        parameter.requires_grad_(False)
    return target


@torch.no_grad()
def advance_target(target,online,retention=.4):
    assert 0<=retention<1
    old=list(target.get_critic_params());new=list(online.get_critic_params())
    assert len(old)==len(new) and old
    for saved,current in zip(old,new):
        assert saved.shape==current.shape
        saved.lerp_(current,1-retention)


def run(root,checkpoint,output,method):
    import supermimic_pilot as pilot
    import supermimic_imagined_exact as imagined
    assert method in ('online','target')
    original_update=imagined.update
    state={'target':None,'steps':0}

    def update(wm,buffer,ctx,actor_opt,critic_opt,scorer,**kwargs):
        if method=='target' and state['target'] is None:
            state['target']=make_target(ctx.a._model)
            state['initial']=[p.clone() for p in state['target'].get_critic_params()]
            assert all(torch.equal(p,q) for p,q in zip(state['initial'],ctx.a._model.get_critic_params()))
            print('TARGET_CRITIC_INITIALIZED',flush=True)
        result=original_update(wm,buffer,ctx,actor_opt,critic_opt,scorer,
                               value_model=state['target'],**kwargs)
        state['steps']+=1
        if method=='target':
            advance_target(state['target'],ctx.a._model)
            params=list(state['target'].get_critic_params())
            result.update(target_retention=.4,target_update_count=state['steps'],
                          target_delta_l2=float(sum((p-q).square().sum() for p,q in zip(params,state['initial'])).sqrt()),
                          target_online_gap_l2=float(sum((p-q).square().sum() for p,q in zip(params,ctx.a._model.get_critic_params())).sqrt()))
        return result

    imagined.update=update
    try:
        pilot.run(root,checkpoint,output,horizon=8,seconds=300,actor_lr=1.125e-6,
                  fast=True,warm_model='increments-audited',stochastic_actor=True,
                  noisy_eval=True,exact_reward=True,actor_batch=1024,eval_interval=90,
                  training_seed=849140,imagined_exact=True,hard_imagined_failure=True,
                  increment_model=True,evaluation_seeds=[984140,984141])
    finally:
        imagined.update=original_update
    path=Path(output)/'result.json';report=json.loads(path.read_text())
    report['target_critic_ablation']=dict(method=method,old_target_retention=.4 if method=='target' else None,
        updates=state['steps'],source_commit='a4c0dd1696d3c3b885ce85a3cb64370b580cb913',
        limitation='Causal short screen against online-critic BPTT, not native-PPO speed proof; normal rows checked only120ticks. Longer native-PPO confirmation required.')
    assert state['steps']>0
    if method=='target':
        assert all(p.grad is None and not p.requires_grad for p in state['target'].parameters())
        torch.save(state['target'].state_dict(),Path(output)/'target_critic_final.pt')
    path.write_text(json.dumps(report,indent=2))
    print('TARGET_CRITIC_COMPLETE',method,state['steps'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for field in ['root','checkpoint','output','method']:parser.add_argument('--'+field,required=True)
    run(**vars(parser.parse_args()))
