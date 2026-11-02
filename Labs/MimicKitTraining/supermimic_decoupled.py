"""Isolated DMO-inspired gradient updates along fresh real-simulator trajectories.

Reference: https://arxiv.org/abs/2509.00215 . This adaptation retains our learned
reward/failure gradients, existing policy, and actual task termination semantics.
It is not the authors' implementation or a production training change.
"""
import copy
import torch
from torch import nn
from torch.nn import functional as F


def anchor(predicted,observed):
    """Exactly observed forward values; only predicted supplies the derivative."""
    return observed.detach()+(predicted-predicted.detach())


def recent_batch(buffer,batch,horizon,fresh_ticks=None):
    fresh_ticks=horizon if fresh_ticks is None else fresh_ticks
    if fresh_ticks<horizon or buffer.count<fresh_ticks:raise ValueError('Insufficient fresh trajectory')
    eligible=torch.arange(buffer.n,device=buffer.device)
    eligible=eligible[eligible%10!=0]
    # All starts must be collected after the last policy change. Sample distinct
    # (world,start tick) pairs, rather than reusing stale off-policy trajectories.
    starts=fresh_ticks-horizon+1
    pairs=torch.randperm(len(eligible)*starts,device=buffer.device)[:batch]
    ids=eligible[pairs%len(eligible)]
    times=(buffer.ptr-fresh_ticks+pairs//len(eligible)+torch.arange(horizon,device=buffer.device)[:,None])%buffer.capacity
    return {k:v[times,ids[None]] for k,v in buffer.data.items()}


def update(wm,buffer,ctx,optimizer,target_model,horizon,batch=128,exact_reward=None,critic_weight=1.,fresh_ticks=None,analytic_failure=False,stop_phase_gradient=False):
    b=recent_batch(buffer,batch,horizon,fresh_ticks);a=ctx.a;e=ctx.e
    x=b['x'][0];history=b['history'][0];phase=b['phase'][0]
    xy_history=b['history_xy'][0] if exact_reward is not None else None
    motion=b['motion'][0];pert=b['pert'][0];n=len(x)
    penalty=pert.float()*(e._gaits[motion]!=-1)*float(e._perturb_cfg['loco_failure_penalty'])
    actor=list(a._model.get_actor_params())
    for p in wm.parameters():p.requires_grad_(False)
    for p in target_model.parameters():p.requires_grad_(False)
    alive=torch.ones(n,device=x.device);objective=torch.zeros_like(alive)
    dense_objective=torch.zeros_like(alive);failure_objective=torch.zeros_like(alive);first_action=None
    phase_loss=0.;bound_loss=0.;mean_errors=[];forward_errors=[];com_errors=[];failure_mismatches=[]
    start_obs=ctx.obs(x,motion,phase).detach()
    with torch.no_grad():old_mean=a._model.eval_actor(start_obs).mode.clone()
    for t in range(horizon):
        raw,_,pred_phase=ctx.policy(x,motion,phase)
        if t==0:first_action=raw
        # These trajectories were collected with these same actor weights.
        # Reconstruct each recorded Gaussian sample, including its clamp mask.
        mean_errors.append(((raw-b['mean_a'][t]).abs()*alive[:,None]).amax())
        raw_sample=raw+(b['raw_a'][t]-raw.detach())
        action=raw_sample.clamp(ctx.low,ctx.high)
        bound_loss+=((raw-raw.clamp(ctx.low,ctx.high)).square().sum(-1)*alive).mean()
        clock=ctx.clock_phase(motion,b['times'][t]+1/30.)
        phase_loss+=((pred_phase-clock).square().mean(-1)*(~pert)*alive).mean()
        predicted_phase=torch.where(pert[:,None],F.normalize(pred_phase,dim=-1,eps=1e-6),clock)
        # PPO does not backpropagate task reward through its deterministic phase
        # head. This ablation retains the same predicted-phase forward values,
        # while allowing only the original normal-row phase supervision.
        phase=b['next_phase'][t].detach() if stop_phase_gradient else anchor(predicted_phase,b['next_phase'][t])
        previous_x=x
        predicted=wm.step(x,action);x=anchor(predicted,b['next_x'][t])
        forward_errors.append((x-b['next_x'][t]).abs().amax())
        history=torch.cat((history[:,1:],x[:,None]),1)
        predicted_reward,logit=wm.heads(history,ctx.head_context(motion,phase,b['age'][t]+1,pert))
        if exact_reward is not None:
            _,_,v,_=exact_reward.bodies(previous_x,xy_history[:,-1])
            _,_,nv,_=exact_reward.bodies(x,xy_history[:,-1])
            xy=anchor(xy_history[:,-1]+(v[:,0,:2]+nv[:,0,:2])*(1/60.),b['next_xy'][t])
            xy_history=torch.cat((xy_history[:,1:],xy[:,None]),1)
            predicted_reward,_=exact_reward(history,xy_history,motion,phase,b['age'][t]+1,b['times'][t]+1/30.,pert)
        actual_reward=b['base_reward'][t]-penalty*b['fail'][t]
        failure_probability=logit.sigmoid()
        if analytic_failure:
            if exact_reward is None:raise ValueError('Analytic failure requires exact reward')
            hard,failure_probability=exact_reward.failure(x,xy,motion,b['age'][t]+1,pert)
            com_errors.append(((exact_reward.com2(x,xy)-b['com2'][t]).abs()*alive[:,None]).amax())
            scoped=pert&(e._gaits[motion]!=-1)&(alive>0)
            failure_mismatches.append(((hard!=b['fail'][t])&scoped).sum())
        reward=anchor(predicted_reward-penalty*failure_probability,actual_reward)
        dense_objective+=.99**t*alive*predicted_reward
        failure_objective+=.99**t*alive*penalty*failure_probability
        objective+=.99**t*alive*reward
        final=(b['done'][t]&~b['fail'][t]) | ((t==horizon-1)&~b['done'][t])
        if critic_weight:
            value=target_model.eval_critic(ctx.obs(x,motion,phase)).squeeze(-1)
            objective+=critic_weight*.99**(t+1)*alive*final*value
        # Hard simulator ends cannot leak gradients/rewards from a reset episode.
        alive=alive*(~b['done'][t])
    mean_error=float(torch.stack(mean_errors).max().detach())
    forward_error=float(torch.stack(forward_errors).max().detach())
    if mean_error>2e-3:raise RuntimeError('Decoupled trajectories are not on policy: '+str(mean_error))
    if forward_error!=0:raise RuntimeError('Decoupled forward values differ from simulator')
    com_error=float(torch.stack(com_errors).max().detach()) if com_errors else 0.
    mismatches=int(torch.stack(failure_mismatches).sum()) if failure_mismatches else 0
    if analytic_failure and (com_error>2e-3 or mismatches):
        raise RuntimeError('Analytic failure does not match simulator: '+str((com_error,mismatches)))
    loss=-objective.mean()+a._phase_weight*phase_loss/horizon+a._action_bound_weight*bound_loss/horizon
    diagnostic={}
    if exact_reward is not None and not optimizer.state:
        dg=torch.autograd.grad(dense_objective.sum(),first_action,retain_graph=True)[0]
        fg=torch.autograd.grad(-failure_objective.sum(),first_action,retain_graph=True)[0]
        diagnostic=dict(first_action_dense_gradient_norm=float(dg.norm().detach()),
            first_action_failure_gradient_norm=float(fg.norm().detach()),
            first_action_gradient_alignment=float((dg*fg).sum().detach()/(dg.norm()*fg.norm()).detach().clamp_min(1e-12)))
    optimizer.zero_grad(set_to_none=True);loss.backward()
    if not optimizer.state and hasattr(a._model,'_phase_out'):
        diagnostic['phase_head_gradient_norm']=float(sum(p.grad.square().sum() for p in a._model._phase_out.parameters() if p.grad is not None).sqrt())
    norm=nn.utils.clip_grad_norm_(actor,1.)
    if not torch.isfinite(norm):raise RuntimeError('Nonfinite decoupled actor gradient')
    for p in actor:
        if p.grad is not None:p.grad.clamp_(-.1,.1)
    before=[p.detach().clone() for p in actor];old_opt=copy.deepcopy(optimizer.state_dict())
    optimizer.step()
    with torch.no_grad():
        dist=a._model.eval_actor(start_obs)
        kl=((dist.mode-old_mean)/dist.stddev).square().sum(-1).mean()*.5
        rejected=float(kl)>.18
        if rejected:
            for p,q in zip(actor,before):p.copy_(q)
            optimizer.load_state_dict(old_opt)
            for group in optimizer.param_groups:group['lr']=max(1e-7,group['lr']*.5)
    for p in wm.parameters():p.requires_grad_(True)
    return dict(actor_loss=float(loss.detach()),actor_grad_norm=float(norm),kl=float(kl),
                rejected=rejected,actor_lr=optimizer.param_groups[0]['lr'],
                actor_batch_size=n,real_forward_max_error=forward_error,on_policy_mean_max_error=mean_error,
                com2_max_error=com_error,failure_class_mismatches=mismatches,**diagnostic)
