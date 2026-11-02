"""Compare anchored and free model advice against matched real episodes, no learning."""
import hashlib
import json
import os
import sys
import threading
import time
import traceback

import torch

import supermimic_race as base
from supermimic_decoupled import anchor
from supermimic_exact_reward import ExactReward
from supermimic_imagined_exact import survival_objective,hard_forward_failure,origin_velocity
from torch.nn import functional as F


def rollout_advice(ctx,wm,exact,init,trajectory,anchored):
    """Same frozen actor/model: isolate learned Jacobian from free-forward error."""
    motion,pert=init['motion'],init['pert'];n=len(motion);horizon=len(trajectory)
    delta=init['obs'].new_zeros((n,34),requires_grad=True)
    x=ctx.physical(init['obs']);phase=init['obs'][:,-2:]
    history,xh=init['history'],init['xy_history']
    histories=[];positions=[];phases=[];observations=[ctx.obs(x,motion,phase)]
    alive=x.new_ones(n);weights=[];quality={};mean_errors=[]
    for t,row in enumerate(trajectory):
        weights.append(alive)
        raw,_,pred=ctx.policy(x,motion,phase)
        mean_errors.append(((raw-row['mean']).abs()*alive[:,None]).amax())
        # Reuse each row's actual exploration draw without anchoring the mean.
        action=(raw+(row['raw']-row['mean'])+(delta if t==0 else 0)).clamp(ctx.low,ctx.high)
        clock=ctx.clock_phase(motion,init['times']+(t+1)/30.)
        phase=torch.where(pert[:,None],F.normalize(pred,dim=-1,eps=1e-6),clock)
        nx=wm.step(x,action)
        if anchored:
            nx=anchor(nx,row['x']);phase=anchor(phase,row['phase'])
        xy=xh[:,-1]+(origin_velocity(ctx,x)[:,:2]+origin_velocity(ctx,nx)[:,:2])/60.
        if anchored:xy=anchor(xy,row['xy'])
        history=torch.cat((history[:,1:],nx[:,None]),1);xh=torch.cat((xh[:,1:],xy[:,None]),1)
        histories.append(history);positions.append(xh);phases.append(phase)
        observations.append(ctx.obs(nx,motion,phase));x=nx
        if t+1 in (1,8,32):
            scope=init['valid']&pert&(ctx.e._gaits[motion]!=-1)&(alive>0)
            expected=ctx.policy(row['x'],motion,row['phase'])[0]
            predicted=ctx.policy(nx,motion,phase)[0]
            quality['h'+str(t+1)]=dict(rows=int(scope.sum()),
                state_nse=float((nx-row['x'])[scope].square().mean().detach()),
                next_action_rmse=float((predicted-expected)[scope].square().mean().sqrt().detach()))
        alive=alive*(~row['done'])
    m=motion.repeat(horizon);p=pert.repeat(horizon)
    age=init['age'][None]+torch.arange(1,horizon+1,device=x.device)[:,None]
    times=init['times'][None]+torch.arange(1,horizon+1,device=x.device)[:,None]/30.
    h=torch.stack(histories).flatten(0,1);xyh=torch.stack(positions).flatten(0,1)
    ph=torch.stack(phases).flatten(0,1)
    dense,_=exact(h,xyh,m,ph,age.flatten(),times.flatten(),p)
    hard,soft=exact.failure(h[:,-1],xyh[:,-1],m,age.flatten(),p)
    logits=wm.terminal(torch.cat((h[:,-1],ctx.head_context(m,ph,age.flatten(),p)),-1)).squeeze(-1)
    fail=torch.where(p,hard_forward_failure(hard,soft),logits.sigmoid()).reshape(horizon,n)
    penalty=pert*(ctx.e._gaits[motion]!=-1)*float(ctx.e._perturb_cfg['loco_failure_penalty'])
    dense=dense.reshape(horizon,n);reward=dense-penalty[None]*fail
    values=ctx.a._model.eval_critic(torch.stack(observations).flatten(0,1)).reshape(horizon+1,n)
    timeout=age>=torch.where(pert,120.,300.)[None]
    full,*_=survival_objective(reward,fail,timeout,values)
    weight=torch.stack(weights);discount=.99**torch.arange(horizon,device=x.device,dtype=x.dtype)
    if anchored:
        actual=torch.stack([r['reward']+penalty*r['fail'] for r in trajectory])
        quality['reward_max_error']=float(((dense-actual).abs()*weight).amax().detach())
        quality['actor_mean_max_error']=float(torch.stack(mean_errors).amax().detach())
        scoped=pert[None]&(ctx.e._gaits[motion][None]!=-1)&(weight>0)
        quality['hard_failure_mismatches']=int(((hard.reshape(horizon,n)!=torch.stack([r['fail'] for r in trajectory]))&scoped).sum())
        if quality['reward_max_error']>.002 or quality['actor_mean_max_error']>.002 or quality['hard_failure_mismatches']:
            raise RuntimeError('Anchored reconstruction does not match real trajectory: '+str(quality))
    return delta,dict(h1_dense=dense[0],dense=(discount[:,None]*weight*dense).sum(0),full=full),quality


def component_directions(objectives, delta):
    gradients = {
        name: torch.autograd.grad(value.sum(), delta, retain_graph=True)[0].detach()
        for name, value in objectives.items()
    }
    for gradient in gradients.values():
        if not torch.isfinite(gradient).all():
            raise RuntimeError('Nonfinite objective derivative')
    directions = {name: g / g.square().mean(-1, keepdim=True).sqrt().clamp_min(1e-8)
                  for name, g in gradients.items()}
    return gradients, directions


def audit(env, agent, ctx, wm, out, horizon, exploration=False, seconds=480):
    import mujoco_warp as mjw
    from envs.base_env import DoneFlags
    from learning.base_agent import AgentMode

    started = time.perf_counter()
    policy_before = [p.detach().clone() for p in agent.parameters()]
    for model in (agent, wm):
        for p in model.parameters():
            p.requires_grad_(False)
    agent.eval()
    agent.set_mode(AgentMode.TEST)
    exact = ExactReward(ctx)
    n, device = env.get_num_envs(), ctx.device
    result = dict(kind='gradient_fidelity_audit', complete=False, exploration=exploration,
                  horizon=horizon, amplitude=.01, seeds=[91871, 92719], probes=[], checks=[],
                  context_captured_before_rollout=True,actor_updates=0,
                  dense_window='Actual control survival held fixed; full objective uses predicted survival',
                  phases='Autoregressive phase differentiation retained; anchored forward matches actual phase')
    state = dict(stage='starting', tick=None, progress=time.monotonic())
    main_thread = threading.get_ident()
    finished = threading.Event()

    def progress(stage, tick=None):
        state.update(stage=stage, tick=tick, progress=time.monotonic())

    def monitor():
        while not finished.wait(20):
            stack = traceback.extract_stack(sys._current_frames()[main_thread])[-8:]
            status = dict(seconds=time.perf_counter()-started, stage=state['stage'], tick=state['tick'],
                          stalled_seconds=time.monotonic()-state['progress'],
                          stack=[dict(file=Path(f.filename).name, line=f.lineno, function=f.name) for f in stack])
            print('FIDELITY_AUDIT_LIVE', json.dumps(status), flush=True)
            if status['stalled_seconds'] > 100 or status['seconds'] > seconds + 10:
                base.write(out/'watchdog.json', status)
                print('FIDELITY_AUDIT_ERROR no progress within bounded stage timeout', flush=True)
                os._exit(3)

    from pathlib import Path
    threading.Thread(target=monitor, daemon=True).start()
    print('FIDELITY_AUDIT_START', json.dumps(dict(exploration=exploration, budget=seconds)), flush=True)

    def check_deadline():
        if time.perf_counter() - started > seconds:
            raise TimeoutError('Objective audit exceeded its bounded budget')

    def real(seed, prefix_ticks, delta=None):
        check_deadline()
        progress('reset')
        with torch.no_grad():
            base.seed(seed)
            mjw.reset_data(env._engine._solver.mjw_model, env._engine._solver.mjw_data)
            obs, info = agent._reset_envs()
            noise = torch.Generator(device=device).manual_seed(seed + 1000000)
            xy = env._engine.get_root_pos(env._get_char_id())[:, :2].clone()
            history = ctx.physical(obs)[:, None].repeat(1, 3, 1)
            xy_history = xy[:, None].repeat(1, 3, 1)
            alive = torch.ones(n, device=device, dtype=torch.bool)
            initial = None
            trajectory = []
            total = torch.zeros(n, device=device)
            short = torch.zeros_like(total)
            first_reward = torch.zeros_like(total)
            discounted = torch.zeros_like(total)
            failed = torch.zeros_like(alive)
            for tick in range(120):
                progress('real rollout', tick)
                if tick == prefix_ticks:
                    initial = dict(obs=obs.clone(), history=history.clone(), xy_history=xy_history.clone(),
                                   valid=alive.clone(), motion=env._motion_ids.clone(), pert=env._perturbed_rows.clone(),
                                   age=torch.round(env._time_buf*30).clone(),
                                   times=(env._time_buf+env._motion_time_offsets).clone())
                    alive = torch.ones_like(alive)
                action, _ = agent._decide_action(obs, info)
                dist = agent._model.eval_actor(agent._obs_norm.normalize(obs))
                raw = base.sample_normalized_action(dist, noise) if exploration else dist.mode
                if tick == prefix_ticks and delta is not None:
                    raw = raw + delta
                action = agent._a_norm.unnormalize(raw.clamp(ctx.low, ctx.high))
                nxt, reward, done, info = env.step(action)
                xy = env._engine.get_root_pos(env._get_char_id())[:, :2].clone()
                x = ctx.physical(nxt)
                ended, fail = done != DoneFlags.NULL.value, done == DoneFlags.FAIL.value
                if tick >= prefix_ticks:
                    t = tick - prefix_ticks
                    if t==0:first_reward=reward.clone()
                    total += alive * reward
                    discounted += .99 ** t * alive * reward
                    if t < horizon:
                        short += .99 ** t * alive * reward
                        trajectory.append(dict(x=x.clone(), xy=xy, phase=nxt[:, -2:].clone(),
                            raw=raw.clone(), mean=dist.mode.clone(), reward=reward.clone(),
                            age=torch.round(env._time_buf * 30).clone(),
                            times=(env._time_buf + env._motion_time_offsets).clone(), done=ended, fail=fail))
                    failed |= alive & fail
                alive &= ~ended
                history = torch.cat((history[:, 1:], x[:, None]), 1)
                xy_history = torch.cat((xy_history[:, 1:], xy[:, None]), 1)
                obs, info = agent._reset_done_envs(done)
                history[ended] = ctx.physical(obs)[ended, None].repeat(1, 3, 1)
                xy_history[ended] = env._engine.get_root_pos(env._get_char_id())[ended, None, :2].repeat(1, 3, 1)
            return dict(initial=initial, trajectory=trajectory, total=total, short=short,
                        discounted=discounted, failed=failed, first_reward=first_reward)

    # Prime lazy simulator state before any matched comparisons.
    real(91879, 8)
    for seed in result['seeds']:
        for prefix_ticks in (8, 40):
            control = real(seed, prefix_ticks)
            init = control['initial']
            motion, pert = init['motion'], init['pert']
            advice={};all_gradients={};checks=dict(seed=seed,prefix_ticks=prefix_ticks,modes={})
            for mode in ['anchored','free']:
                progress(mode+' differentiable rollout')
                delta,objectives,quality=rollout_advice(ctx,wm,exact,init,control['trajectory'],mode=='anchored')
                chosen=({'anchored_h1_dense':objectives['h1_dense'], 'anchored_h32_dense':objectives['dense']}
                        if mode=='anchored' else {'free_h32_dense':objectives['dense'],'free_h32_full':objectives['full']})
                gradients,directions=component_directions(chosen,delta)
                quality['gradient_norms']={k:float(v.norm()) for k,v in gradients.items()}
                checks['modes'][mode]=quality;advice.update(directions);all_gradients.update(gradients)
                del delta,objectives,chosen,gradients
            result['checks'].append(checks)
            print('FIDELITY_AUDIT_CHECK',json.dumps(checks),flush=True)
            candidates = {}
            common = init['valid'] & pert & (env._gaits[motion] != -1)
            control_hash=hashlib.sha256(init['obs'].cpu().numpy().tobytes()).hexdigest()
            for name, direction in advice.items():
                positive = real(seed, prefix_ticks, .01 * direction)
                negative = real(seed, prefix_ticks, -.01 * direction)
                mismatch = torch.stack([(r['initial']['obs'] - init['obs']).abs().amax(-1)
                                        for r in (positive, negative)]).amax(0)
                valid = common & positive['initial']['valid'] & negative['initial']['valid'] & (mismatch < 2e-4)
                candidates[name] = dict(positive=positive, negative=negative, valid=valid)
                common &= valid
            if int(common.sum()) < 32:
                raise RuntimeError('Too few identical surviving starts across objective probes')
            for name, pair in candidates.items():
                p, m = pair['positive'], pair['negative']
                d = p['discounted'] - m['discounted']
                row = dict(seed=seed, prefix_ticks=prefix_ticks, component=name, rows=int(common.sum()),
                           initial_observation_sha256=control_hash,
                           mean_discounted_return_change=float(d[common].mean()),
                           median_discounted_return_change=float(d[common].median()),
                           positive_fraction=float((d[common] > 0).float().mean()),
                           mean_return_change=float((p['total'] - m['total'])[common].mean()),
                           short_return_change=float((p['short'] - m['short'])[common].mean()),
                           first_reward_change=float((p['first_reward']-m['first_reward'])[common].mean()),
                           predicted_linear_change=float((.02*all_gradients[name]*advice[name]).sum(-1)[common].mean()),
                           positive_failures=int(p['failed'][common].sum()), negative_failures=int(m['failed'][common].sum()),
                           row_valid=common.cpu().tolist(), row_motion=motion.cpu().tolist(),
                           row_first_reward_delta=(p['first_reward']-m['first_reward']).cpu().tolist(),
                           row_short_return_delta=(p['short']-m['short']).cpu().tolist(),
                           row_predicted_linear_change=(.02*all_gradients[name]*advice[name]).sum(-1).cpu().tolist(),
                           row_return_delta=d.cpu().tolist(), row_failure_delta=(p['failed'].int() - m['failed'].int()).cpu().tolist())
                result['probes'].append(row)
                print('FIDELITY_AUDIT_PROBE', json.dumps({k: v for k, v in row.items() if not k.startswith('row_')}), flush=True)
            base.write(out / 'result.json', result)
    change = float(sum((p.detach() - q).square().sum() for p, q in zip(agent.parameters(), policy_before)).sqrt())
    assert change == 0.
    finished.set()
    result.update(complete=True, policy_parameter_delta_l2=change, seconds=time.perf_counter() - started)
    base.write(out / 'result.json', result)
    print('FIDELITY_AUDIT_COMPLETE', json.dumps({k: v for k, v in result.items() if k not in ('probes', 'checks')}), flush=True)
    return result
