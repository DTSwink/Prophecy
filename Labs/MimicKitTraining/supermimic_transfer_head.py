"""SuperTrack-inspired final-layer transfer versus full-actor model gradients.

This isolates freezing pretrained actor features. It is not a SuperTrack
reproduction: original MimicKit task, learned increment model and phase remain.
"""
import argparse
import json
from pathlib import Path
import torch


def constrain_actor(model,method):
    assert method in ('full','heads')
    before={k:v.detach().clone() for k,v in model._actor_layers.state_dict().items()}
    if method=='heads':model._actor_layers.requires_grad_(False)
    assert any(p.requires_grad for p in model._action_dist.parameters())
    assert all(p.requires_grad for p in model._phase_out.parameters())
    # The production Gaussian has a fixed, non-trainable logstd Parameter.
    allowed={id(p) for module in [model._action_dist,model._phase_out] for p in module.parameters() if p.requires_grad}
    if method=='heads':assert all(p.requires_grad==(id(p) in allowed) for p in model.get_actor_params())
    return before


def feature_delta(model,before):
    return max(float((v-model._actor_layers.state_dict()[k]).abs().max()) for k,v in before.items())


def run(root,checkpoint,output,method):
    import supermimic_pilot as pilot
    import supermimic_race as base
    import supermimic_imagined_exact as imagined
    original_context=base.Context;original_update=imagined.update;state={}
    class TransferContext(original_context):
        def __init__(self,env,agent):
            super().__init__(env,agent)
            state.update(model=agent._model,features=constrain_actor(agent._model,method),updates=0)
            state['initial_heads']={k:v.detach().clone() for k,v in agent._model.state_dict().items() if k.startswith(('_action_dist.','_phase_out.'))}
            counts={name:sum(p.numel() for p in module.parameters() if p.requires_grad)
                    for name,module in [('features',agent._model._actor_layers),('motor',agent._model._action_dist),('phase',agent._model._phase_out)]}
            state['trainable_counts']=counts
            print('TRANSFER_HEAD_READY',json.dumps(dict(method=method,trainable_counts=counts)),flush=True)
    def update(*args,**kwargs):
        result=original_update(*args,**kwargs);state['updates']+=1
        delta=feature_delta(state['model'],state['features'])
        if method=='heads':
            assert delta==0 and all(p.grad is None for p in state['model']._actor_layers.parameters())
        result['transfer_feature_max_abs_delta']=delta
        result['transfer_motor_grad_norm']=float(sum((p.grad.square().sum() for p in state['model']._action_dist.parameters() if p.grad is not None),torch.zeros((),device='cuda:0')).sqrt())
        return result
    base.Context=TransferContext;imagined.update=update
    try:
        pilot.run(root,checkpoint,output,horizon=8,seconds=240,actor_lr=1.125e-6,
                  fast=True,warm_model='increments-audited',stochastic_actor=True,
                  noisy_eval=True,exact_reward=True,actor_batch=1024,eval_interval=75,
                  training_seed=849190,imagined_exact=True,hard_imagined_failure=True,
                  increment_model=True,evaluation_seeds=[984190,984191])
    finally:
        base.Context=original_context;imagined.update=original_update
    path=Path(output)/'result.json';report=json.loads(path.read_text())
    model=state['model'];delta=feature_delta(model,state['features'])
    heads_delta=float(sum((v-model.state_dict()[k]).square().sum() for k,v in state['initial_heads'].items()).sqrt())
    assert state['updates']>0 and heads_delta>0
    if method=='heads':assert delta==0
    report['output_layer_transfer']=dict(method=method,feature_max_abs_delta=delta,head_parameter_delta_l2=heads_delta,
        updates=state['updates'],trainable_counts=state['trainable_counts'],
        scope='Frozen actor hidden layers; motor and phase output layers train. Input-state gradients still flow through frozen features. World/critic fitting unchanged.',
        limitation='Controlled short comparison with full-actor model gradients, not native PPO speed proof.120tick normal-row screen requires full300tick confirmation before promotion.',
        primary_source='SuperTrack section5.2, https://static-wordpress.akamaized.net/montreal.ubisoft.com/wp-content/uploads/2021/11/24183638/SuperTrack.pdf')
    path.write_text(json.dumps(report,indent=2));print('TRANSFER_HEAD_COMPLETE',method,state['updates'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ['root','checkpoint','output','method']:p.add_argument('--'+key,required=True)
    run(**vars(p.parse_args()))
