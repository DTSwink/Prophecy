"""Read-only audit of task context absent from the retained PPO critic input."""
import torch


@torch.no_grad()
def audit(ctx,buffer,scorer):
    b=buffer.sample(1024,1,holdout=True)
    x=b['next_x'][0];phase=b['next_phase'][0];motion=b['motion'][0];pert=b['pert'][0]
    history=torch.cat((b['history'][0,:,1:],x[:,None]),1)
    xy=torch.cat((b['history_xy'][0,:,1:],b['next_xy'][0,:,None]),1)
    # Same full state/history/reference phase. Only the hidden task clock differs.
    # These are counterfactual contexts, not claims that every duplicated state
    # has equal visitation probability at every age under the current policy.
    obs=ctx.obs(x,motion,phase)
    result=dict(kind='critic_context_alias_audit',rows=int(pert.sum()),
        critic_inputs=list(('physical_state','commands','phase')),
        absent_inputs=['episode_age','normal_or_perturbed_flag','three_frame_AE_history'],
        counterfactual_only=True,causal_training_failure_not_established=True,ages=[10,45,75])
    rewards=[];values=[]
    for age in result['ages']:
        r,_=scorer(history,xy,motion,phase,torch.full_like(b['age'][0],age),b['times'][0]+1/30.,pert)
        rewards.append(r);values.append(ctx.a._model.eval_critic(obs).flatten())
    result['critic_value_max_change']=float((torch.stack(values)-values[0]).abs().max())
    spread=torch.stack(rewards).amax(0)-torch.stack(rewards).amin(0)
    result['perturbed_reward_range_mean']=float(spread[pert].mean())
    result['perturbed_reward_range_p90']=float(torch.quantile(spread[pert],.9))
    result['perturbed_reward_range_max']=float(spread[pert].max())
    result['perturbed_fraction_reward_change_gt_01']=float((spread[pert]>.01).float().mean())
    assert result['critic_value_max_change']==0
    return result
