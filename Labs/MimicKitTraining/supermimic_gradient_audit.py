"""Check imagined action gradients against paired real-simulator interventions.

No policy/model optimization. Every intervention replays the same seeded prefix.
The test measures local return derivatives, not long-term learning performance.
"""
import json,time
import numpy as np
import torch
from torch.nn import functional as F
import supermimic_race as base


def audit(env,agent,ctx,wm,out,horizon):
    import mujoco_warp as mjw
    from learning.base_agent import AgentMode
    from envs.base_env import DoneFlags
    for p in agent.parameters():p.requires_grad_(False)
    for p in wm.parameters():p.requires_grad_(False)
    agent.eval();agent.set_mode(AgentMode.TEST)
    started=time.perf_counter();result=dict(kind='gradient_audit',horizon=horizon,complete=False,probes=[])
    gamma=.99;N=env.get_num_envs()

    def prefix(seed,ticks):
        base.seed(seed);mjw.reset_data(env._engine._solver.mjw_model,env._engine._solver.mjw_data)
        obs,info=agent._reset_envs();history=ctx.physical(obs)[:,None].repeat(1,3,1)
        alive=torch.ones(N,device=obs.device,dtype=torch.bool)
        with torch.no_grad():
            for _ in range(ticks):
                action,_=agent._decide_action(obs,info)
                nxt,_,done,info=env.step(action)
                history=torch.cat((history[:,1:],ctx.physical(nxt)[:,None]),1)
                alive &= done==DoneFlags.NULL.value
                obs,info=agent._reset_done_envs(done)
        return obs.clone(),info,history,alive

    def imagine(x,history,motion,phase,age,times,pert,delta):
        survival=torch.ones(N,device=x.device);total=torch.zeros_like(survival)
        penalty=pert*(env._gaits[motion]!=-1)*float(env._perturb_cfg['loco_failure_penalty'])
        for t in range(horizon):
            raw,action,prediction=ctx.policy(x,motion,phase)
            if t==0:action=(raw+delta).clamp(ctx.low,ctx.high)
            clock=ctx.clock_phase(motion,times+(t+1)/30.)
            phase=torch.where(pert[:,None],F.normalize(prediction,dim=-1,eps=1e-6),clock)
            x=wm.step(x,action);history=torch.cat((history[:,1:],x[:,None]),1)
            reward,logit=wm.heads(history,ctx.head_context(motion,phase,age+t+1,pert))
            fail=logit.sigmoid();timeout=age+t+1>=torch.where(pert,120.,300.)
            value=agent._model.eval_critic(ctx.obs(x,motion,phase)).squeeze(-1)
            total+=gamma**t*survival*(reward-penalty*fail+gamma*(1-fail)*timeout*value)
            survival=survival*(1-fail)*(~timeout)
        return total+gamma**horizon*survival*value

    def real(seed,ticks,delta):
        obs,info,_,alive=prefix(seed,ticks);start=obs.clone()
        active=torch.ones(N,device=obs.device,dtype=torch.bool)
        total=torch.zeros(N,device=obs.device);rewards=total.clone();bootstrap=total.clone()
        with torch.no_grad():
            for t in range(horizon):
                action,_=agent._decide_action(obs,info)
                if t==0:action=agent._a_norm.unnormalize((agent._a_norm.normalize(action)+delta).clamp(ctx.low,ctx.high))
                nxt,reward,done,info=env.step(action)
                value=agent._model.eval_critic(agent._obs_norm.normalize(nxt)).squeeze(-1)
                rewards+=gamma**t*reward*active
                timeout=(done!=DoneFlags.NULL.value)&(done!=DoneFlags.FAIL.value)
                bootstrap+=gamma**(t+1)*active*timeout*value
                active &= done==DoneFlags.NULL.value
                obs,info=agent._reset_done_envs(done)
            bootstrap+=gamma**horizon*active*value
        return dict(objective=rewards+bootstrap,reward=rewards,bootstrap=bootstrap,
                    start=start,alive=alive)

    # Prime lazy simulator state before comparing reset observations.
    prefix(91871,8)
    for ticks in [8,40]:
        seed=91871+ticks
        obs,info,history,valid=prefix(seed,ticks)
        x=ctx.physical(obs).detach();history=history.detach()
        motion=env._motion_ids.clone();phase=obs[:,-2:].clone()
        age=torch.round(env._time_buf*30).clone();times=(env._time_buf+env._motion_time_offsets).clone()
        pert=env._perturbed_rows.clone();loco=env._gaits[motion]!=-1
        zero=torch.zeros((N,34),device=obs.device)
        delta=zero.clone().requires_grad_(True)
        predicted=imagine(x,history,motion,phase,age,times,pert,delta)
        gradient=torch.autograd.grad(predicted.sum(),delta)[0].detach()
        if not torch.isfinite(gradient).all():raise RuntimeError('Nonfinite audit action gradient')
        direction=gradient/gradient.square().mean(-1,keepdim=True).sqrt().clamp_min(1e-8)
        control=real(seed,ticks,zero)
        for amplitude in [.01,.04]:
            positive=real(seed,ticks,amplitude*direction)
            negative=real(seed,ticks,-amplitude*direction)
            mismatch=torch.stack([(v['start']-obs).abs().amax(-1) for v in [control,positive,negative]]).amax(0)
            matched=valid & control['alive'] & positive['alive'] & negative['alive'] & (mismatch<2e-4)
            with torch.no_grad():
                pred_delta=imagine(x,history,motion,phase,age,times,pert,amplitude*direction)-imagine(x,history,motion,phase,age,times,pert,-amplitude*direction)
            difference=positive['objective']-negative['objective']
            groups={}
            for name,mask in [('perturbed_loco',matched&pert&loco),('normal_loco',matched&~pert&loco)]:
                n=int(mask.sum());a=difference[mask].cpu().numpy()
                rng=np.random.default_rng(8421);boot=np.array([rng.choice(a,len(a),replace=True).mean() for _ in range(1000)]) if n else np.array([np.nan])
                groups[name]=dict(rows=n,predicted_mean_change=float(pred_delta[mask].mean()),
                    real_mean_change=float(difference[mask].mean()),positive_real_fraction=float((difference[mask]>0).float().mean()),
                    paired_reward_change=float((positive['reward']-negative['reward'])[mask].mean()),
                    paired_bootstrap_change=float((positive['bootstrap']-negative['bootstrap'])[mask].mean()),
                    episode_bootstrap_95=np.quantile(boot,[.025,.975]).tolist())
            row=dict(prefix_ticks=ticks,action_rms_perturbation=amplitude,matched_rows=int(matched.sum()),
                     initial_state_max_error=float(mismatch.max()),groups=groups,
                     row_group=(pert.long()*2+(~loco).long()).cpu().tolist(),row_motion=motion.cpu().tolist(),
                     row_valid=matched.cpu().tolist(),row_predicted_delta=pred_delta.cpu().tolist(),
                     row_real_delta=difference.cpu().tolist())
            result['probes'].append(row);base.write(out/'result.json',result)
            print('GRADIENT_AUDIT',json.dumps({k:v for k,v in row.items() if not k.startswith('row_')}),flush=True)
    result.update(complete=True,seconds=time.perf_counter()-started)
    base.write(out/'result.json',result);print('GRADIENT_AUDIT_COMPLETE',result['seconds'],flush=True)
    return result
