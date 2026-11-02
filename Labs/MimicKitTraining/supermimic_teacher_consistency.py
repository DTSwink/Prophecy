"""Independent native-planner target consistency and mean-action probe.

Search a small decaying motor-action residual over the first8ticks. Rank using
actual32tick MuJoCo reward plus frozen critic bootstrap, then independently
evaluate the selected residual over120ticks, with and without exploration.
No learned dynamics, parameter updates, modified task or full-episode oracle.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import torch
import supermimic_race as base


def elite_distribution(candidates, scores, elites=2, minimum=.02, maximum=.15):
    """Batched form of Judo CEM's elite mean and bounded population std."""
    assert candidates.ndim == 3 and scores.shape == candidates.shape[:2]
    ids = scores.topk(elites, dim=0).indices
    chosen = candidates.gather(0, ids[..., None].expand(-1, -1, candidates.shape[-1]))
    return chosen.mean(0), chosen.var(0, unbiased=False).sqrt().clamp(minimum, maximum)


def accumulate(active, failed, returns, discounted, reward, done, fail, tick, gamma=.99):
    return (active & ~done, failed | (active & fail), returns + active*reward,
            discounted + gamma**tick*active*reward)


def residual_scale(tick):
    return max(0., 1.-tick/8.)


def pack(seed, groups, motion, failed, returns, ticks, initial_hash):
    names=['normal_loco','normal_idle','perturbed_loco','perturbed_idle']
    return dict(seed=seed,row_group=groups.cpu().tolist(),row_motion=motion.cpu().tolist(),
                row_failed=failed.cpu().tolist(),row_return=returns.cpu().tolist(),
                row_ticks=ticks.cpu().tolist(),initial_observation_sha256=initial_hash,
                groups={name:dict(rows=int((groups==i).sum()),failures=int(failed[groups==i].sum()),
                                  mean_return=float(returns[groups==i].mean())) for i,name in enumerate(names)})


def run(root, checkpoint, output, seed):
    started=time.perf_counter();seed=int(seed)
    root=Path(root).resolve();output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    sys.path[:0]=[str(root/'pipeline'),str(root/'MimicKit/mimickit')];os.chdir(root/'MimicKit')
    os.environ['PYGLET_HEADLESS']='true';torch.set_num_threads(2)
    import warp as wp,yaml,mujoco_warp as mjw
    from util import mp_util
    from perturbed_omni import PerturbedOmniEnv
    from omni_policy import OmniPPOAgent
    from resume import restore,migrate_physical_observation_scales
    from learning.base_agent import AgentMode
    from envs.base_env import DoneFlags
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6841)
    base.seed(849110)
    cfg,ec,ac=[yaml.safe_load((root/'prepared'/(n+'_config.yaml')).read_text()) for n in ['env','engine','agent']]
    env=PerturbedOmniEnv(cfg,ec,1024,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0')
    restored=restore(agent,checkpoint)
    if cfg.get('perturbed_motion',{}).get('observation_normalization')=='physical_scales_v1':
        migrate_physical_observation_scales(agent)
    agent._init_train();assert not agent._need_normalizer_update()
    agent.eval();agent.set_mode(AgentMode.TEST)
    initial={k:v.detach().clone() for k,v in agent.state_dict().items()}
    for p in agent.parameters():p.requires_grad_(False)
    device='cuda:0';n=1024;zero=torch.zeros(n,34,device=device)
    reset_obs=None;reset_motion=None;reset_groups=None;reset_errors=[]
    first_trace=None;repeat_traces=[];repeat_scores=[]
    report=dict(kind='native_teacher_consistency_screen',complete=False,seed=seed,
                checkpoint_sha256=hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest(),
                gpu=torch.cuda.get_device_name(),actor_updates=0,restored=restored,
                planning_horizon=32,residual_ticks=8,candidates_per_round=8,rounds=2,independent_searches=2,
                initial_sigma=.075,elite_count=2,scope='Perturbed locomotion only',
                planning=[],evaluations={},interpretation='Per-state planning feasibility only, not a learned policy or training-speed gain. No selection uses120tick outcomes.')
    base.write(output/'result.json',report)

    @torch.no_grad()
    def rollout(bias, horizon, noisy=False, prime=False, audit_repeat=False):
        nonlocal reset_obs,reset_motion,reset_groups,first_trace
        if time.perf_counter()-started>500:raise TimeoutError('Bounded planning screen expired')
        base.seed(seed if not prime else seed+10)
        mjw.reset_data(env._engine._solver.mjw_model,env._engine._solver.mjw_data)
        obs,info=agent._reset_envs()
        motion=env._motion_ids.clone()
        groups=env._perturbed_rows.long()*2+(env._gaits[motion]==-1).long()
        if not prime:
            if reset_obs is None:reset_obs=obs.clone();reset_motion=motion.clone();reset_groups=groups.clone()
            error=float((obs-reset_obs).abs().max());reset_errors.append(error)
            assert error<2e-4 and torch.equal(motion,reset_motion) and torch.equal(groups,reset_groups), ('Reset mismatch',error)
        scope=groups==2;bias=bias*scope[:,None]
        observation_hash=hashlib.sha256(obs.cpu().numpy().tobytes()).hexdigest()
        active=torch.ones(n,device=device,dtype=torch.bool);failed=torch.zeros_like(active)
        total=torch.zeros(n,device=device);discounted=torch.zeros_like(total);bootstrap=torch.zeros_like(total)
        ticks=torch.zeros(n,device=device,dtype=torch.long)
        noise=torch.Generator(device=device).manual_seed(seed+2000000)
        beyond=torch.zeros_like(total);after32_failure=torch.zeros_like(active);trace=[]
        for tick in range(horizon):
            agent._decide_action(obs,info)  # Preserve production next-phase feedback.
            dist=agent._model.eval_actor(agent._obs_norm.normalize(obs))
            raw=base.sample_normalized_action(dist,noise) if noisy else dist.mode
            raw=raw+residual_scale(tick)*bias
            if audit_repeat:trace.append((obs.clone(),raw.clone()))
            nxt,reward,done,info=env.step(agent._a_norm.unnormalize(raw))
            ended=done!=DoneFlags.NULL.value;fail=done==DoneFlags.FAIL.value
            assert torch.isfinite(reward).all()
            if tick>=32:
                beyond+=active*reward;after32_failure|=active&fail
            ticks+=active
            value=agent._model.eval_critic(agent._obs_norm.normalize(nxt)).squeeze(-1)
            bootstrap+=.99**(tick+1)*active*ended*(~fail)*value
            active,failed,total,discounted=accumulate(active,failed,total,discounted,reward,ended,fail,tick)
            obs,info=agent._reset_done_envs(done)
        # Value is the pre-reset final observation's value, not a reset state's.
        score=discounted+bootstrap+.99**horizon*active*value
        assert torch.isfinite(score).all()
        evaluation=pack(seed,groups,motion,failed,total,ticks,observation_hash)
        evaluation.update(row_post32_return=beyond.cpu().tolist(),row_post32_failure=after32_failure.cpu().tolist())
        if audit_repeat:
            if first_trace is None:first_trace=trace
            item=dict(obs_max_by_tick=[float((x-a).abs().max()) for (x,y),(a,b) in zip(trace,first_trace)],
                      action_max_by_tick=[float((y-b).abs().max()) for (x,y),(a,b) in zip(trace,first_trace)],
                      failed=failed.cpu().tolist(),score=score.cpu().tolist())
            repeat_traces.append(item);repeat_scores.append(score.clone())
            print('PLANNING_REPEAT',json.dumps(dict(repeat=len(repeat_traces),obs_max=max(item['obs_max_by_tick']),action_max=max(item['action_max_by_tick']),failures=int(failed[scope].sum()))),flush=True)
        return score,evaluation

    # Prime lazy simulator caches before comparing any reset.
    rollout(zero,8,prime=True)
    report['setup_seconds']=time.perf_counter()-started
    planning_started=time.perf_counter()
    for _ in range(3):rollout(zero,32,audit_repeat=True)
    report['zero_repeat_diagnostics']=repeat_traces
    base.write(output/'result.json',report)
    winners=[];selection_scores=[];control_scores=[];round_zero_differences=[]
    for search_id in range(2):
        generator=torch.Generator(device=device).manual_seed(seed+3000000+search_id*100000)
        mean=zero.clone();sigma=torch.full_like(mean,.075);best=zero.clone();best_score=None;zero_score=None
        for round_id in range(2):
            sampled=mean[None]+sigma[None]*torch.randn((6,n,34),device=device,generator=generator)
            sampled=sampled.clamp(-.225,.225)
            candidates=torch.cat((zero[None],best[None],sampled),0)
            scores=[]
            for candidate_id,bias in enumerate(candidates):
                score,ev=rollout(bias,32);scores.append(score)
                scope=reset_groups==2
                record=dict(search=search_id,round=round_id,candidate=candidate_id,seconds=time.perf_counter()-planning_started,
                            mean_score=float(score[scope].mean()),short_failure_percent=ev['groups']['perturbed_loco']['failures']/int(scope.sum())*100)
                report['planning'].append(record)
                print('PLANNING_PROGRESS',json.dumps(record),flush=True)
            scores=torch.stack(scores)
            if zero_score is None:zero_score=scores[0].clone()
            else:round_zero_differences.append(dict(search=search_id,
                max_abs=float((zero_score-scores[0]).abs().max()),
                mean_abs=float((zero_score-scores[0]).abs().mean())))
            winner=scores.argmax(0);row=torch.arange(n,device=device)
            best=candidates[winner,row].clone();best_score=scores[winner,row]
            mean,sigma=elite_distribution(candidates,scores)
            base.write(output/'result.json',report)
        winners.append(best.clone());selection_scores.append(best_score.clone());control_scores.append(zero_score)
    report['round_zero_differences']=round_zero_differences
    scope=reset_groups==2;a,b=[x[scope] for x in winners]
    cosine=torch.nn.functional.cosine_similarity(a,b,dim=-1)
    avg=(winners[0]+winners[1])*.5
    report['consistency']=dict(
        residual_cosine_mean=float(cosine.mean()),
        residual_cosine_quantiles=torch.quantile(cosine,torch.tensor([0.,.25,.5,.75,1.],device=device)).tolist(),
        averaged_target_energy_ratio=float(((a+b)*.5).square().sum()/(.5*(a.square().sum()+b.square().sum()))),
        different_zero_choice_fraction=float(((a.abs().sum(-1)==0)!=(b.abs().sum(-1)==0)).float().mean()),
        note='Different successful actions can be multimodal; cosine alone does not establish teacher failure.')
    avg_score,_=rollout(avg,32)
    import numpy as np
    np.savez_compressed(output/'teacher_consistency.npz',observation=reset_obs.cpu().numpy(),groups=reset_groups.cpu().numpy(),
        residual_a=winners[0].cpu().numpy(),residual_b=winners[1].cpu().numpy(),
        score_a=selection_scores[0].cpu().numpy(),score_b=selection_scores[1].cpu().numpy(),
        score_zero=control_scores[0].cpu().numpy(),score_zero_b=control_scores[1].cpu().numpy(),
        zero_repeat_scores=torch.stack(repeat_scores).cpu().numpy(),score_mean=avg_score.cpu().numpy())
    report.update(planning_seconds=time.perf_counter()-planning_started)
    print('PLANNING_CONSISTENCY',json.dumps(report['consistency']),flush=True)
    # Selection is irrevocably finished. Fresh production noise is never used by CEM.
    for noisy in [False,True]:
        label='noisy' if noisy else 'deterministic'
        report['evaluations'][label]={}
        for name,bias in [('control',zero),('winner_a',winners[0]),('winner_b',winners[1]),('mean',avg)]:
            _,evaluation=rollout(bias,120,noisy=noisy)
            report['evaluations'][label][name]=dict(rows=[evaluation])
            print('PLANNING_EVALUATION',json.dumps(dict(seed=seed,mode=label,arm=name,groups=evaluation['groups'])),flush=True)
            base.write(output/'result.json',report)
    delta=max(float((v-initial[k]).abs().max()) for k,v in agent.state_dict().items())
    assert delta==0
    report.update(complete=True,policy_max_abs_delta=delta,reset_max_abs_error=max(reset_errors),
                  total_seconds=time.perf_counter()-started)
    base.write(output/'result.json',report)
    print('PLANNING_COMPLETE',seed,report['total_seconds'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ['root','checkpoint','output','seed']:p.add_argument('--'+key,required=True)
    run(**vars(p.parse_args()))
