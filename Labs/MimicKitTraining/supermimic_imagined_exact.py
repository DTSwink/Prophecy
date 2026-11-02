"""Fully imagined BPTT with the audited analytic task reward, experiments only.

Earlier exact-reward pilots anchored forward states to real trajectories. This
module instead rolls the model forward freely, like SuperMimic Algorithm A.1.
Task rewards are unchanged. COM2 uses a smooth analytic failure surrogate;
normal-row termination still uses the fitted classifier. This is an adaptation.
"""
import copy
import torch
from torch import nn
from torch.nn import functional as F
from supermimic_race import lambda_targets
from supermimic_structured import matrix_from_six


def hard_forward_failure(hard,soft):
    """Exact terminal event forward; smooth surrogate derivative backward.

    Unlike a probability-weighted terminal cost this cannot tax successful
    transitions. Critic targets detach it, so they use only actual hard events
    in the predicted trajectory. This remains a biased surrogate gradient.
    """
    return hard.to(soft.dtype)+(soft-soft.detach())


def survival_objective(rewards, failures, timeouts, values, gamma=.99):
    """Count the terminal reward once, bootstrap timeouts, never failed states."""
    continuation=(1-failures)*(~timeouts)
    before=torch.cat((torch.ones_like(continuation[:1]),continuation[:-1].cumprod(0)),0)
    after=continuation.prod(0)
    timeout_value=(1-failures)*timeouts*values[1:]
    discount=gamma**torch.arange(len(rewards),device=rewards.device,dtype=rewards.dtype)
    objective=(discount[:,None]*before*(rewards+gamma*timeout_value)).sum(0)
    return objective+gamma**len(rewards)*after*values[-1],before,continuation,timeout_value


def origin_velocity(ctx,x):
    raw=x*ctx.std[:146]+ctx.mean[:146]
    offset=(matrix_from_six(raw[:,1:7])@ctx.e._body_com[0,0,:,None]).squeeze(-1)
    return raw[:,7:10]-torch.cross(raw[:,10:13],offset,dim=-1)


def validate_real_reward(ctx,buffer,scorer,hard_failure=False):
    """Reject a scoring mismatch before any candidate actor update."""
    b=buffer.sample(1024,1,holdout=True)
    with torch.no_grad():
        history=torch.cat((b['history'][0,:,1:],b['next_x'][0,:,None]),1)
        xy=torch.cat((b['history_xy'][0,:,1:],b['next_xy'][0,:,None]),1)
        reward,_=scorer(history,xy,b['motion'][0],b['next_phase'][0],b['age'][0]+1,
                        b['times'][0]+1/30.,b['pert'][0])
        error=(reward-b['base_reward'][0]).abs()
        hard,soft=scorer.failure(b['next_x'][0],b['next_xy'][0],b['motion'][0],
                              b['age'][0]+1,b['pert'][0])
        scoped=b['pert'][0]&(ctx.e._gaits[b['motion'][0]]!=-1)
        mismatches=int(((hard!=b['fail'][0])&scoped).sum())
        penalty=float(ctx.e._perturb_cfg['loco_failure_penalty'])
        actual=b['base_reward'][0]-penalty*b['fail'][0]
        terminal=hard_forward_failure(hard,soft) if hard_failure else soft
        total_error=(reward-penalty*terminal-actual)[scoped]
        surviving=scoped&~b['fail'][0]
    result=dict(reward_max_abs=float(error.max()),reward_mean_abs=float(error.mean()),
                reciprocal_derivative_median=float(reward.square().median()),
                reciprocal_derivative_q10=float(reward.square().quantile(.1)),
                reciprocal_derivative_q90=float(reward.square().quantile(.9)),
                perturbed_loco_failure_mismatches=mismatches,
                perturbed_total_reward_max_abs=float(total_error.abs().max()),
                surviving_soft_penalty_mean=float((penalty*soft)[surviving].mean()),
                hard_forward_failure=hard_failure)
    if result['reward_max_abs']>.002 or result['reward_mean_abs']>.0002 or mismatches:
        raise RuntimeError('Imagined exact-score real-data validation failed: '+str(result))
    if hard_failure and result['perturbed_total_reward_max_abs']>.002:
        raise RuntimeError('Hard-forward terminal reward differs from simulator: '+str(result))
    return result


def phase_feedback(prediction,clock,perturbed,stop_gradient=False):
    """Keep actual autoregressive phase, optionally detach only its task gradient."""
    feedback=prediction.detach() if stop_gradient else prediction
    return torch.where(perturbed[:,None],F.normalize(feedback,dim=-1,eps=1e-6),clock)


def direct_tracking_reward(reward,terms,scale):
    """Original reward forward; fixed-scale raw tracking-cost gradient backward.

    This tests supervised tracking gradients inspired by SuperTrack, not an
    exact reproduction. Scale is fixed once from the median real-data reciprocal
    derivative. Survival derivatives and critic targets retain original rewards.
    """
    cost=terms.sum(-1)
    return reward.detach()+float(scale)*(cost.detach()-cost)


def update(wm,buffer,ctx,actor_opt,critic_opt,scorer,batch=1024,horizon=16,hard_failure=False,critic_weight=1.,stochastic_actor=False,stop_phase_gradient=False,direct_tracking_gradient=False,value_model=None):
    assert critic_weight in (0.,1.), 'Controlled critic-on/off ablation only'
    b=buffer.sample(batch,1);a=ctx.a;e=ctx.e
    x=b['x'][0];history=b['history'][0];xy_history=b['history_xy'][0]
    motion=b['motion'][0];phase=b['phase'][0];pert=b['pert'][0]
    age=b['age'][0];times=b['times'][0]
    contextual=hasattr(a._model,'_loco_critic_context')
    bootstrap_model=a._model if value_model is None else value_model
    if value_model is not None:
        assert critic_weight and not contextual, 'Target-critic screen uses the original critic architecture'
        assert all(not p.requires_grad for p in value_model.parameters())
    if contextual:
        from supermimic_value_context import parameters,features,evaluate
        critic=parameters(a._model)
    else:critic=list(a._model.get_critic_params())
    actor=list(a._model.get_actor_params())
    for p in wm.parameters():p.requires_grad_(False)
    for p in critic:p.requires_grad_(False)
    start_obs=ctx.obs(x,motion,phase).detach()
    with torch.no_grad():old_mean=a._model.eval_actor(start_obs).mode.clone()
    observations=[ctx.obs(x,motion,phase)];histories=[];xys=[];phases=[];ages=[]
    bounds=[];phase_errors=[];noise_square=[]
    for t in range(horizon):
        raw,action,pred_phase=(ctx.policy(x,motion,phase,sample_actions=True) if stochastic_actor
                               else ctx.policy(x,motion,phase))
        noise_square.append((action.detach()-raw.detach().clamp(ctx.low,ctx.high)).square().mean())
        next_clock=ctx.clock_phase(motion,times+(t+1)/30.)
        bounds.append((raw-raw.clamp(ctx.low,ctx.high)).square().sum(-1))
        phase_errors.append((pred_phase-next_clock).square().mean(-1)*(~pert))
        phase=phase_feedback(pred_phase,next_clock,pert,stop_phase_gradient)
        nx=wm.step(x,action)
        xy=xy_history[:,-1]+(origin_velocity(ctx,x)[:,:2]+origin_velocity(ctx,nx)[:,:2])/60.
        history=torch.cat((history[:,1:],nx[:,None]),1)
        xy_history=torch.cat((xy_history[:,1:],xy[:,None]),1)
        x=nx
        histories.append(history);xys.append(xy_history);phases.append(phase);ages.append(age+t+1)
        observations.append(ctx.obs(x,motion,phase))
    # Batch FK, AE, reference interpolation, and critic evaluation over time.
    # This preserves BPTT while avoiding a separate small scorer call every tick.
    h=torch.stack(histories).flatten(0,1);xyh=torch.stack(xys).flatten(0,1)
    m=motion.repeat(horizon);p=pert.repeat(horizon);ph=torch.stack(phases).flatten(0,1)
    ag=torch.stack(ages).flatten();tm=(times[None]+torch.arange(1,horizon+1,device=x.device)[:,None]/30.).flatten()
    dense,terms=scorer(h,xyh,m,ph,ag,tm,p)
    tracking_scale=getattr(wm,'_direct_tracking_scale',None)
    if direct_tracking_gradient:
        assert tracking_scale is not None and 0<tracking_scale<=1
        dense=direct_tracking_reward(dense,terms,tracking_scale)
    hard,analytic_fail=scorer.failure(h[:,-1],xyh[:,-1],m,ag,p)
    if hard_failure:analytic_fail=hard_forward_failure(hard,analytic_fail)
    logits=wm.terminal(torch.cat((h[:,-1],ctx.head_context(m,ph,ag,p)),-1)).squeeze(-1)
    failure=torch.where(p,analytic_fail,logits.sigmoid()).reshape(horizon,batch)
    penalty=pert*(e._gaits[motion]!=-1)*float(e._perturb_cfg['loco_failure_penalty'])
    reward=dense.reshape(horizon,batch)-penalty[None]*failure
    timeout=torch.stack(ages)>=torch.where(pert,120.,300.)[None]
    obs=torch.stack(observations)
    value_context=(features(e,torch.cat((age[None],torch.stack(ages))),pert[None].expand(horizon+1,-1))
                   if contextual else None)
    if critic_weight:
        values=(evaluate(a._model,obs.flatten(0,1),value_context.flatten(0,1)) if contextual
                else bootstrap_model.eval_critic(obs.flatten(0,1))).reshape(horizon+1,batch)
    else:values=x.new_zeros((horizon+1,batch))
    objective,weights,continuation,timeout_value=survival_objective(reward,failure,timeout,values)
    loss=-objective.mean()+a._phase_weight*(torch.stack(phase_errors)*weights.detach()).mean()
    loss=loss+a._action_bound_weight*(torch.stack(bounds)*weights.detach()).mean()
    actor_opt.zero_grad(set_to_none=True);loss.backward()
    phase_grad_norm=(float(sum((p.grad.square().sum() for p in a._model._phase_out.parameters()
                               if p.grad is not None),x.new_zeros(())).sqrt())
                     if hasattr(a._model,'_phase_out') else None)
    norm=nn.utils.clip_grad_norm_(actor,1.)
    if not torch.isfinite(norm):raise RuntimeError('Nonfinite fully imagined actor gradient')
    for param in actor:
        if param.grad is not None:param.grad.clamp_(-.1,.1)
    before=[p.detach().clone() for p in actor];saved_opt=copy.deepcopy(actor_opt.state_dict())
    actor_opt.step()
    with torch.no_grad():
        dist=a._model.eval_actor(start_obs)
        kl=((dist.mode-old_mean)/dist.stddev).square().sum(-1).mean()*.5
        rejected=float(kl)>.18
        if rejected:
            for param,old in zip(actor,before):param.copy_(old)
            actor_opt.load_state_dict(saved_opt)
            for group in actor_opt.param_groups:group['lr']=max(1e-7,group['lr']*.5)
        targets=lambda_targets(reward.detach(),continuation.detach(),timeout_value.detach(),values.detach()).flatten()
        critic_obs=obs[:-1].detach().flatten(0,1);sample_weights=weights.detach().flatten()
        critic_context=value_context[:-1].detach().flatten(0,1) if contextual else None
    for p in critic:p.requires_grad_(True)
    vl=x.new_zeros(())
    for _ in range(5 if critic_weight else 0):
        for ids in torch.randperm(len(targets),device=x.device).chunk(4):
            prediction=(evaluate(a._model,critic_obs[ids],critic_context[ids]) if contextual
                        else a._model.eval_critic(critic_obs[ids])).flatten()
            vl=((prediction-targets[ids]).square()*sample_weights[ids]).sum()/sample_weights[ids].sum().clamp_min(1e-6)
            critic_opt.zero_grad(set_to_none=True);vl.backward()
            gn=nn.utils.clip_grad_norm_(critic,1.)
            if not torch.isfinite(gn):raise RuntimeError('Nonfinite imagined critic gradient')
            critic_opt.step()
    for p in wm.parameters():p.requires_grad_(True)
    return dict(actor_loss=float(loss.detach()),critic_loss=float(vl.detach()),actor_grad_norm=float(norm),
                actor_batch_size=batch,actor_lr=actor_opt.param_groups[0]['lr'],kl=float(kl),rejected=rejected,
                imagined_dense_reward=float(dense.detach().mean()),imagined_failure_probability=float(failure.detach().mean()),
                imagined_survival_end=float(continuation.detach().prod(0).mean()),
                imagined_terminal_value=float(values[-1].detach().mean()),forward_mode='free_model_rollout',
                hard_forward_failure=hard_failure,critic_enabled=bool(critic_weight),
                separate_bootstrap_critic=value_model is not None,
                critic_task_context=contextual,
                stochastic_imagination=stochastic_actor,
                stop_phase_gradient=stop_phase_gradient,phase_head_gradient_norm=phase_grad_norm,
                direct_tracking_gradient=direct_tracking_gradient,
                direct_tracking_scale=tracking_scale if direct_tracking_gradient else None,
                imagined_action_noise_rms=float(torch.stack(noise_square).mean().sqrt()),
                critic_context_weight_l2=(float(a._model._loco_critic_context.weight.detach().norm()) if contextual else 0.))
