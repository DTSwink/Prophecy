"""Frozen real/model calibration, using identical branch states and action noise.

No learning or policy selection. Compare logged-control and closed-loop model
predictions at 1/4/8/16/32 ticks against real MuJoCo, including terminal rewards.
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
from supermimic_imagined_exact import origin_velocity, phase_feedback

HORIZONS=(1,4,8,16,32)
BRANCHES=(0,24,56,80)
GROUPS=('normal_loco','normal_idle','perturbed_loco','perturbed_idle')


def cohort_step(active, failed, returns, reward, fail, ended):
    """Include terminal reward once; post-reset frames never enter the cohort."""
    return active & ~ended, failed | (active & fail), returns + reward*active


def expected_step(survival,failure,returns,dense,penalty,probability,timeout):
    """Marginalize the first terminal event; its penalty is charged only once."""
    return (survival*(1-probability)*~timeout,
            failure+survival*probability,
            returns+survival*(dense-penalty*probability))


def summarize(valid, real_failed, predicted_failed, real_return, predicted_return):
    n=int(valid.sum())
    if not n:return dict(rows=0)
    actual=real_failed[valid];predicted=predicted_failed[valid]
    return dict(rows=n,real_failures=int(actual.sum()),predicted_failures=int(predicted.sum()),
        false_positive=int((predicted&~actual).sum()),false_negative=int((actual&~predicted).sum()),
        real_failure_percent=100*float(actual.float().mean()),
        predicted_failure_percent=100*float(predicted.float().mean()),
        real_return=float(real_return[valid].mean()),predicted_return=float(predicted_return[valid].mean()),
        return_mae=float((real_return[valid]-predicted_return[valid]).abs().mean()))


@torch.no_grad()
def capture(ctx, scorer, seed, noisy):
    from learning.base_agent import AgentMode
    from envs.base_env import DoneFlags
    import mujoco_warp as mjw
    env,agent=ctx.e,ctx.a
    agent.eval();agent.set_mode(AgentMode.TEST);base.seed(seed)
    mjw.reset_data(env._engine._solver.mjw_model,env._engine._solver.mjw_data)
    obs,info=agent._reset_envs();n=len(obs)
    rng=torch.Generator(device=obs.device).manual_seed(seed+1000000)
    history=ctx.physical(obs)[:,None].repeat(1,3,1)
    xy=env._engine.get_root_pos(env._get_char_id())[:,:2].clone()
    history_xy=xy[:,None].repeat(1,3,1)
    active=torch.ones(n,device=obs.device,dtype=torch.bool)
    group=env._perturbed_rows.long()*2+(env._gaits[env._motion_ids]==-1).long()
    rows=[];max_reward_error=0.;mismatch=0
    for tick in range(120):
        row=dict(x=ctx.physical(obs).clone(),history=history.clone(),history_xy=history_xy.clone(),
            motion=env._motion_ids.clone(),phase=obs[:,-2:].clone(),pert=env._perturbed_rows.clone(),
            age=torch.round(env._time_buf*30).clone(),times=(env._time_buf+env._motion_time_offsets).clone(),
            valid=active.clone())
        agent._decide_action(obs,info)
        dist=agent._model.eval_actor(agent._obs_norm.normalize(obs))
        epsilon=torch.randn(dist.mode.shape,device=obs.device,generator=rng) if noisy else torch.zeros_like(dist.mode)
        normalized=dist.mode+dist.stddev*epsilon
        action=agent._a_norm.unnormalize(normalized)
        nxt,reward,done,info=env.step(action)
        nx=ctx.physical(nxt);xy=env._engine.get_root_pos(env._get_char_id())[:,:2].clone()
        history=torch.cat((history[:,1:],nx[:,None]),1)
        history_xy=torch.cat((history_xy[:,1:],xy[:,None]),1)
        fail=done==DoneFlags.FAIL.value;ended=done!=DoneFlags.NULL.value
        penalty=row['pert']*(env._gaits[row['motion']]!=-1)*float(env._perturb_cfg['loco_failure_penalty'])
        dense,_=scorer(history,history_xy,row['motion'],nxt[:,-2:],row['age']+1,row['times']+1/30.,row['pert'])
        hard,_=scorer.failure(nx,xy,row['motion'],row['age']+1,row['pert'])
        if active.any():max_reward_error=max(max_reward_error,float((dense-penalty*fail-reward)[active].abs().max()))
        mismatch+=int(((hard!=fail)&active&row['pert']&(env._gaits[row['motion']]!=-1)).sum())
        row.update(action=normalized.clamp(ctx.low,ctx.high).clone(),epsilon=epsilon,next_x=nx.clone(),
            next_phase=nxt[:,-2:].clone(),next_xy=xy,reward=reward.clone(),fail=fail.clone(),ended=ended.clone())
        rows.append(row);active &= ~ended
        obs,info=agent._reset_done_envs(done)
        history[ended]=ctx.physical(obs)[ended,None].repeat(1,3,1)
        history_xy[ended]=env._engine.get_root_pos(env._get_char_id())[ended,None,:2].repeat(1,3,1)
    assert max_reward_error<.002 and mismatch==0,(max_reward_error,mismatch)
    print('CALIBRATION_REAL',json.dumps(dict(seed=seed,noisy=noisy,score_max_error=max_reward_error,hard_event_mismatches=mismatch)),flush=True)
    return rows,group,dict(score_max_error=max_reward_error,hard_event_mismatches=mismatch)


@torch.no_grad()
def predict(ctx,wm,scorer,rows,group,branch,closed_loop,seed):
    if hasattr(wm,'begin_from_rows'):wm.begin_from_rows(rows,branch)
    first=rows[branch];x=first['x'].clone();phase=first['phase'].clone()
    history=first['history'].clone();history_xy=first['history_xy'].clone()
    motion,pert=first['motion'],first['pert'];valid=first['valid']
    pa=valid.clone();ra=valid.clone();pf=torch.zeros_like(valid);rf=pf.clone()
    pr=torch.zeros(len(x),device=x.device);rr=pr.clone();out=[]
    expected_survival=valid.float();expected_failure=torch.zeros_like(pr);expected_return=torch.zeros_like(pr)
    generator=torch.Generator(device=x.device).manual_seed(seed+2000000+branch)
    penalty=pert*(ctx.e._gaits[motion]!=-1)*float(ctx.e._perturb_cfg['loco_failure_penalty'])
    for offset in range(32):
        real=rows[branch+offset];norm_obs=ctx.obs(x,motion,phase)
        dist=ctx.a._model.eval_actor(norm_obs)
        action=(dist.mode+dist.stddev*real['epsilon']).clamp(ctx.low,ctx.high) if closed_loop else real['action']
        age=first['age']+offset+1;times=first['times']+(offset+1)/30.
        phase=phase_feedback(ctx.a._model.eval_phase(norm_obs),ctx.clock_phase(motion,times),pert) if closed_loop else real['next_phase']
        nx=wm.step(x,action)
        xy=history_xy[:,-1]+(origin_velocity(ctx,x)[:,:2]+origin_velocity(ctx,nx)[:,:2])/60.
        history=torch.cat((history[:,1:],nx[:,None]),1);history_xy=torch.cat((history_xy[:,1:],xy[:,None]),1)
        dense,_=scorer(history,history_xy,motion,phase,age,times,pert)
        hard,_=scorer.failure(nx,xy,motion,age,pert)
        probability=wm.terminal(torch.cat((nx,ctx.head_context(motion,phase,age,pert)),-1)).squeeze(-1).sigmoid()
        sampled=torch.rand(probability.shape,device=x.device,generator=generator)<probability
        if getattr(wm,'_failure_mode','analytic')=='learned':
            enabled=pert&(ctx.e._gaits[motion]!=-1)&(age>ctx.e._perturb_cfg['grace_ticks'])
            fail=torch.where(pert,sampled&enabled,sampled)
            event_probability=torch.where(pert,probability*enabled,probability)
        else:
            fail=torch.where(pert,hard,sampled)
            event_probability=torch.where(pert,hard.float(),probability)
        timeout=age>=torch.where(pert,120.,300.)
        ended=fail|timeout
        expected_survival,expected_failure,expected_return=expected_step(
            expected_survival,expected_failure,expected_return,dense,penalty,event_probability,timeout)
        # Logged controls cease to be a continuation of this motion after its
        # real episode ends. Censor that diagnostic at the real endpoint.
        if not closed_loop:
            ended=ended|real['ended'];expected_survival*=~real['ended']
        before_real=ra.clone();before_predicted=pa.clone()
        pa,pf,pr=cohort_step(pa,pf,pr,dense-penalty*fail,fail,ended)
        ra,rf,rr=cohort_step(ra,rf,rr,real['reward'],real['fail'],real['ended'])
        h=offset+1
        if h in HORIZONS:
            if not torch.isfinite(nx[valid]).all():raise RuntimeError('Nonfinite model trajectory')
            groups={}
            for g,name in enumerate(GROUPS):
                mask=valid&(group==g);item=summarize(mask,rf,pf,rr,pr)
                if mask.any():
                    item['expected_failure_percent']=100*float(expected_failure[mask].mean())
                    item['failure_brier_score']=float((expected_failure[mask]-rf[mask].float()).square().mean())
                    item['expected_return_mae']=float((expected_return[mask]-rr[mask]).abs().mean())
                observed=mask&before_real;both=observed&before_predicted
                item['real_alive_for_state_error']=int(observed.sum());item['both_alive_for_state_error']=int(both.sum())
                if observed.any():
                    item['state_nse_real_alive']=float((nx-real['next_x']).square().mean(-1)[observed].mean())
                    item['root_height_mae_m']=float(((nx-real['next_x'])[:,0]*ctx.std[0]).abs()[observed].mean())
                    item['root_velocity_rmse_mps']=float((((nx-real['next_x'])[:,7:10]*ctx.std[7:10]).square().sum(-1))[observed].mean().sqrt())
                if both.any():item['state_nse_both_alive']=float((nx-real['next_x']).square().mean(-1)[both].mean())
                groups[name]=item
            out.append(dict(branch=branch,horizon=h,closed_loop=closed_loop,groups=groups))
        x=nx
    return out


def run(root,checkpoint,output,policy,model_file,policy_file,failure_mode='analytic'):
    started=time.perf_counter();root=Path(root).resolve();output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    sys.path[:0]=[str(root/'pipeline'),str(root/'MimicKit/mimickit')];os.chdir(root/'MimicKit')
    os.environ['PYGLET_HEADLESS']='true';torch.set_num_threads(2)
    import warp as wp,yaml
    from util import mp_util
    from perturbed_omni import PerturbedOmniEnv
    from omni_policy import OmniPPOAgent
    from resume import restore,migrate_physical_observation_scales
    from supermimic_increments import IncrementWorld
    from supermimic_exact_reward import ExactReward
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6872);base.seed(57361)
    cfg,ec,ac=[yaml.safe_load((root/'prepared'/(n+'_config.yaml')).read_text()) for n in ['env','engine','agent']]
    env=PerturbedOmniEnv(cfg,ec,1024,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0')
    restore(agent,checkpoint)
    if policy=='final':agent.load_state_dict(torch.load(policy_file,map_location='cuda:0',weights_only=True))
    elif policy!='initial':raise ValueError(policy)
    if cfg['perturbed_motion'].get('observation_normalization')=='physical_scales_v1':migrate_physical_observation_scales(agent)
    agent._init_train();agent.eval();initial={k:v.detach().clone() for k,v in agent.state_dict().items()}
    ctx=base.Context(env,agent);wm=IncrementWorld(ctx.mean,ctx.std,ctx.dim,env._kin_char_model,env._key_body_ids).cuda()
    wm.load_state_dict(torch.load(model_file,map_location='cuda:0',weights_only=True)['model']);wm.eval()
    assert failure_mode in ('analytic','learned');wm._failure_mode=failure_mode
    assert int(wm.norm_count)>0
    original_world={k:v.detach().clone() for k,v in wm.state_dict().items()};scorer=ExactReward(ctx)
    report=dict(kind='closed_loop_calibration',complete=False,policy=policy,failure_mode=failure_mode,actor_updates=0,
        setup_seconds=time.perf_counter()-started,branches=BRANCHES,horizons=HORIZONS,
        world_sha256=hashlib.sha256(Path(model_file).read_bytes()).hexdigest(),
        policy_file_sha256=hashlib.sha256(Path(policy_file).read_bytes()).hexdigest(),runs=[])
    print('CALIBRATION_STARTED',json.dumps({k:v for k,v in report.items() if k!='runs'}),flush=True)
    for seed in [683101,683102]:
        for noisy in [False,True]:
            rows,group,validation=capture(ctx,scorer,seed,noisy);predictions=[]
            for branch in BRANCHES:
                for closed in [False,True]:predictions.extend(predict(ctx,wm,scorer,rows,group,branch,closed,seed))
            report['runs'].append(dict(seed=seed,exploration=noisy,validation=validation,predictions=predictions))
            base.write(output/'result.json',report)
            preview=[dict(horizon=r['horizon'],**r['groups']['perturbed_loco']) for r in predictions if r['branch']==0 and r['closed_loop']]
            print('CALIBRATION_PROGRESS',json.dumps(dict(policy=policy,seed=seed,noisy=noisy,branch0_closed_loop=preview)),flush=True)
    model_delta=max(float((v-initial[k]).abs().max()) for k,v in agent.state_dict().items())
    world_delta=max(float((v-original_world[k]).abs().max()) for k,v in wm.state_dict().items())
    assert model_delta==world_delta==0
    report.update(complete=True,policy_max_abs_delta=model_delta,world_max_abs_delta=world_delta,total_seconds=time.perf_counter()-started)
    base.write(output/'result.json',report);print('CALIBRATION_COMPLETE',policy,report['total_seconds'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ['root','checkpoint','output','policy','model_file','policy_file']:p.add_argument('--'+k.replace('_','-'),required=True)
    p.add_argument('--failure-mode',default='analytic',choices=['analytic','learned'])
    a=p.parse_args();run(**vars(a))
