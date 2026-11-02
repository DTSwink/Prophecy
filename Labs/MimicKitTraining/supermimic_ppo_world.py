"""PPO on learned-model rollouts: isolate prediction quality from BPTT quality.

Motivated by the PPO-WM control in SuperMimic §4.2. This adapts its principle to
the frozen Prophecy task and uses the pinned native PPO targets/loss/optimizers.
All imagined data is detached; no world-model derivative reaches the actor.
"""
import argparse
from functools import partial
import json
import time
from pathlib import Path

import torch
import supermimic_race as base
import supermimic_pilot as pilot
from supermimic_imagined_exact import origin_velocity, phase_feedback


def raw_observation(ctx, x, motion, phase):
    return torch.cat((x*ctx.std[:146]+ctx.mean[:146], ctx.commands(motion, phase)), -1)


def done_and_reward(dense, failure, timeout, penalty):
    from envs.base_env import DoneFlags
    # Failure has precedence over timeout; terminal penalty is charged once.
    done = torch.full_like(failure, DoneFlags.NULL.value, dtype=torch.int32)
    done = torch.where(timeout, DoneFlags.TIME.value, done)
    done = torch.where(failure, DoneFlags.FAIL.value, done)
    return done, dense-penalty*failure


@torch.no_grad()
def imagined_rollout(wm, replay, ctx, scorer, horizon=32, batch=1024, branch_horizon=None):
    from learning.experience_buffer import ExperienceBuffer
    agent, env = ctx.a, ctx.e
    if branch_horizon is not None:assert 0<branch_horizon<=horizon and horizon%branch_horizon==0
    exp = ExperienceBuffer(horizon, batch, ctx.device)
    keys = ['x','history','history_xy','motion','phase','age','times','pert']
    def starts():
        b = replay.sample(batch, 1)
        return {k:b[k][0].clone() for k in keys}
    state = starts()
    failures = torch.zeros((),device=ctx.device,dtype=torch.long)
    timeouts = failures.clone()
    branch_cuts = failures.clone()
    for tick in range(horizon):
        x, motion, phase, pert = (state[k] for k in ['x','motion','phase','pert'])
        obs = raw_observation(ctx, x, motion, phase)
        norm_obs = agent._obs_norm.normalize(obs)
        dist = agent._model.eval_actor(norm_obs)
        sampled = base.sample_normalized_action(dist)
        action = agent._a_norm.unnormalize(sampled)
        executed = sampled.clamp(ctx.low, ctx.high)
        clock = ctx.clock_phase(motion, state['times']+1/30.)
        next_phase = phase_feedback(agent._model.eval_phase(norm_obs), clock, pert)
        nx = wm.step(x, executed)
        xy = state['history_xy'][:,-1]+(origin_velocity(ctx,x)[:,:2]+origin_velocity(ctx,nx)[:,:2])/60.
        history = torch.cat((state['history'][:,1:], nx[:,None]),1)
        history_xy = torch.cat((state['history_xy'][:,1:], xy[:,None]),1)
        age, times = state['age']+1, state['times']+1/30.
        dense, _ = scorer(history, history_xy, motion, next_phase, age, times, pert)
        hard, _ = scorer.failure(nx, xy, motion, age, pert)
        logits = wm.terminal(torch.cat((nx,ctx.head_context(motion,next_phase,age,pert)),-1)).squeeze(-1)
        # Learned normal-row termination is sampled, rather than treating a
        # low predicted probability as a sure failure on every step.
        failure = torch.where(pert, hard, torch.rand_like(logits)<logits.sigmoid())
        timeout = age>=torch.where(pert,120.,300.)
        cut=branch_horizon is not None and (tick+1)%branch_horizon==0
        if cut:
            branch_cuts += (~failure&~timeout).sum()
            # Artificial segment boundary bootstraps the final predicted state;
            # it never becomes a failure or receives the failure penalty.
            timeout=torch.ones_like(timeout)
        penalty = pert*(env._gaits[motion]!=-1)*float(env._perturb_cfg['loco_failure_penalty'])
        done, reward = done_and_reward(dense, failure, timeout, penalty)
        row = dict(obs=obs, action=action, a_logp=dist.log_prob(sampled),
            rand_action_mask=torch.ones_like(reward), reward=reward, done=done,
            next_obs=raw_observation(ctx,nx,motion,next_phase),
            next_phase=clock, phase_supervision=(~pert).float())
        for k,v in row.items():exp.record(k,v)
        exp.inc()
        failures += failure.sum(); timeouts += (timeout&~failure).sum()
        state.update(x=nx,phase=next_phase,age=age,times=times,history=history,history_xy=history_xy)
        ended = failure|timeout
        if ended.any():
            reset = starts()
            for k in keys:state[k][ended] = reset[k][ended]
    assert exp.get_sample_count()==batch*horizon
    assert all(not v.requires_grad for v in exp._buffers.values())
    if not torch.stack([v.isfinite().all() for v in exp._buffers.values()]).all():
        raise RuntimeError('Nonfinite imagined PPO rollout')
    return exp, dict(imagined_failures=int(failures),imagined_timeouts=int(timeouts),
        imagined_reward_mean=float(exp.get_data('reward').mean()),imagined_transitions=batch*horizon,
        branch_horizon=branch_horizon or horizon,imagined_branch_cuts=int(branch_cuts))


def update(wm, replay, ctx, actor_opt, critic_opt, scorer, batch=1024, horizon=32, branch_horizon=None, **kwargs):
    agent=ctx.a
    validation_horizon=horizon
    # The pilot's horizon also controls the held-out model gate. For short
    # branches match that gate to8ticks, while retaining native32tick batch size.
    if branch_horizon is not None:
        assert horizon==branch_horizon
        horizon=agent._steps_per_iter
    assert batch==agent.get_num_envs() and horizon==agent._steps_per_iter
    agent.eval()
    started=time.perf_counter()
    exp, metrics=imagined_rollout(wm,replay,ctx,scorer,horizon,batch,branch_horizon)
    rollout_seconds=time.perf_counter()-started
    old_buffer=agent._exp_buffer
    before=[p.detach().clone() for p in agent._model.get_actor_params()]
    try:
        agent._exp_buffer=exp
        train_data=agent._build_train_data()
        # Same native critic updates, actor loss, phase mask, Adam moments and
        # transactional full-rollout KL guard as the real-PPO control.
        trained=agent._update_model()
    finally:
        agent._exp_buffer=old_buffer
    delta=float(sum((p.detach()-q).square().sum() for p,q in zip(agent._model.get_actor_params(),before)).sqrt())
    metrics.update({k:float(v) for k,v in {**train_data,**trained}.items()})
    metrics.update(rejected=delta==0., actor_step_delta_l2=delta,
        model_validation_horizon=validation_horizon,
        actor_batch_size=batch,actor_lr=agent._actor_optimizer._optimizer.param_groups[0]['lr'],
        forward_mode='native_ppo_learned_rollout', world_derivatives_used=False,
        imagined_rollout_seconds=rollout_seconds,ppo_update_seconds=time.perf_counter()-started-rollout_seconds)
    if not hasattr(wm,'_ppo_world_verified'):
        assert delta>0, 'First imagined PPO update did not change actor'
        print('PPO_WORLD_VERIFIED',json.dumps(metrics),flush=True)
        wm._ppo_world_verified=True
    return metrics


def run(root, checkpoint, output, method, seconds=300, seed=57361):
    is_world=method in ('ppo_world','ppo_short')
    if is_world:
        import supermimic_imagined_exact
        supermimic_imagined_exact.update=partial(update,branch_horizon=8) if method=='ppo_short' else update
    elif method!='ppo':raise ValueError(method)
    pilot.run(root,checkpoint,output,horizon=8 if method=='ppo_short' else 32,seconds=seconds,actor_lr=1.125e-6,
        fast=True,native_ppo=method=='ppo',noisy_eval=True,increment_model=is_world,
        imagined_exact=is_world,exact_reward=is_world,
        hard_imagined_failure=is_world,actor_batch=1024,
        warm_model='increments-audited' if is_world else None,
        eval_interval=75,training_seed=seed)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ['root','checkpoint','output','method']:p.add_argument('--'+k,required=True)
    p.add_argument('--seconds',type=float,default=300)
    p.add_argument('--seed',type=int,default=57361)
    a=p.parse_args();run(a.root,a.checkpoint,a.output,a.method,a.seconds,a.seed)
