"""Bounded frozen-model action ranking with calibrated ensemble disagreement.

MOPO-style pessimism adapted to existing normalized physical coordinates.
This is a teacher-feasibility/speed test, not policy learning or a reproduction.
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
from supermimic_rwm_history import RecurrentCorrection
from supermimic_increments import IncrementWorld,apply_increments
from supermimic_imagined_exact import origin_velocity,phase_feedback
from supermimic_planning_probe import residual_scale,accumulate,pack


def max_disagreement(states):
    """Maximum ensemble distance from its mean, not spread of raw increments."""
    return (states-states.mean(0)).square().sum(-1).sqrt().amax(0)


def calibrate(predicted,actual,uncertainty,training_rows):
    """Fit nonnegative optimism-per-disagreement on training worlds only."""
    error=(predicted-predicted[:1])-(actual-actual[:1])
    u=uncertainty-uncertainty[:1]
    x=u[:,training_rows].flatten().double();y=error[:,training_rows].flatten().double()
    coefficient=max(0.,float((x*y).sum()/x.square().sum().clamp_min(1e-12)))
    adjusted=predicted-coefficient*uncertainty
    result=dict(coefficient=coefficient,training_rows=int(training_rows.sum()),heldout_rows=int((~training_rows).sum()),
                units='Discounted score units per discounted normalized next-state ensemble distance',splits={})
    for name,mask in [('train',training_rows),('heldout',~training_rows)]:
        assert bool(mask.any())
        e=error[:,mask].flatten();v=u[:,mask].flatten();real=actual[:,mask]
        ids=torch.arange(real.shape[1],device=real.device)
        raw=predicted[:,mask].argmax(0);safe=adjusted[:,mask].argmax(0)
        result['splits'][name]=dict(
            relative_optimism_mae=float(e.abs().mean()),adjusted_relative_optimism_mae=float((e-coefficient*v).abs().mean()),
            uncertainty_optimism_correlation=float(torch.corrcoef(torch.stack((v,e)))[0,1]) if float(v.std())>1e-9 and float(e.std())>1e-9 else None,
            raw_selected_true_score=float(real[raw,ids].mean()),adjusted_selected_true_score=float(real[safe,ids].mean()),
            zero_true_score=float(real[0].mean()),oracle_true_score=float(real.max(0).values.mean()))
    return result


class UncertainWorld(RecurrentCorrection):
    def step(self,x,a):
        raw=x*self.warm.std+self.warm.mean;f=self.features(x,a)
        y=self.core(f[:,:146,None].transpose(1,2),f[:,146:,None].transpose(1,2))
        zero=y.new_zeros((len(y),1,86));means=torch.stack([head(y,zero)[0] for head in self.heads])
        base_delta=self.warm.dynamics(f)
        deltas=(base_delta[None]+means)*self.warm.delta_std+self.warm.delta_mean
        states=self.warm.skeleton(apply_increments(raw.repeat(len(means),1),deltas.flatten(0,1)))
        states=((states-self.warm.mean)/self.warm.std).reshape(len(means),len(raw),-1)
        self.uncertainty=max_disagreement(states)
        delta=(base_delta+means.mean(0))*self.warm.delta_std+self.warm.delta_mean
        return (self.warm.skeleton(apply_increments(raw,delta))-self.warm.mean)/self.warm.std


def run(root,checkpoint,output,source,model_file,seed,calibration_owner=False):
    start=time.perf_counter();seed=int(seed);root=Path(root).resolve();output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    sys.path[:0]=[str(root/'pipeline'),str(root/'MimicKit/mimickit')];os.chdir(root/'MimicKit')
    os.environ['PYGLET_HEADLESS']='true';torch.set_num_threads(2)
    import warp as wp,yaml,mujoco_warp as mjw
    from util import mp_util
    from perturbed_omni import PerturbedOmniEnv
    from omni_policy import OmniPPOAgent
    from resume import restore,migrate_physical_observation_scales
    from learning.base_agent import AgentMode
    from envs.base_env import DoneFlags
    from supermimic_exact_reward import ExactReward
    def emit(marker,**item):print(marker,json.dumps(item),flush=True)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6844);base.seed(849180)
    cfg,ec,ac=[yaml.safe_load((root/'prepared'/(n+'_config.yaml')).read_text()) for n in ['env','engine','agent']]
    env=PerturbedOmniEnv(cfg,ec,1024,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0');restore(agent,checkpoint)
    if cfg['perturbed_motion'].get('observation_normalization')=='physical_scales_v1':migrate_physical_observation_scales(agent)
    agent._init_train();agent.eval();agent.set_mode(AgentMode.TEST);agent.requires_grad_(False)
    initial={k:v.detach().clone() for k,v in agent.state_dict().items()};ctx=base.Context(env,agent);scorer=ExactReward(ctx)
    warm=IncrementWorld(ctx.mean,ctx.std,ctx.dim,env._kin_char_model,env._key_body_ids).cuda()
    wm=UncertainWorld(warm,source).cuda()
    digest=hashlib.sha256(Path(model_file).read_bytes()).hexdigest()
    assert digest=='0f0c6ca2bc1b53b410350db0b2f8cdd468ae52f3e3bc98fedb9e4c14ee2e0bb9'
    wm.load_state_dict(torch.load(model_file,map_location='cuda:0',weights_only=False)['model'],strict=True)
    wm.eval();wm.requires_grad_(False)
    assert torch.equal(wm.warm.mean,ctx.mean[:146]) and torch.equal(wm.warm.std,ctx.std[:146])
    original_world={k:v.detach().clone() for k,v in wm.state_dict().items()}
    zero=torch.zeros(1024,34,device='cuda:0');refs={};reset_error=0.;score_error=0.;event_mismatch=0;parity_done=False
    report=dict(kind='uncertain_model_planning_screen',seed=seed,complete=False,actor_updates=0,model_updates=0,
        gpu=torch.cuda.get_device_name(),checkpoint_sha256=hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest(),
        model_sha256=digest,prior_model_preparation_seconds=326.300588+24.322178864+180.57724445,
        scope='Only perturbed locomotion receives first8tick residual; normal/idle unchanged',
        candidates=16,horizon=32,residual_ticks=8,evaluation_ticks=120,evaluations={},
        limitations='Frozen-model teacher ranking screen. No learned-policy speedup. Five heads share a recurrent trunk; uncertainty is not a guaranteed error bound. Prior model fitting remains charged.')

    @torch.no_grad()
    def native(reset_seed,bias,horizon,noisy=False,audit=False):
        nonlocal reset_error,score_error,event_mismatch
        base.seed(reset_seed);mjw.reset_data(env._engine._solver.mjw_model,env._engine._solver.mjw_data)
        obs,info=agent._reset_envs();motion=env._motion_ids.clone();pert=env._perturbed_rows.clone()
        groups=pert.long()*2+(env._gaits[motion]==-1).long();scope=groups==2
        if reset_seed not in refs:refs[reset_seed]=(obs.clone(),motion.clone(),groups.clone())
        error=float((obs-refs[reset_seed][0]).abs().max());reset_error=max(reset_error,error)
        assert error<2e-4 and torch.equal(motion,refs[reset_seed][1]) and torch.equal(groups,refs[reset_seed][2])
        first=dict(x=ctx.physical(obs).clone(),phase=obs[:,-2:].clone(),motion=motion,pert=pert,
            xy=env._engine.get_root_pos(env._get_char_id())[:,:2].clone(),age=torch.round(env._time_buf*30).clone(),
            times=(env._time_buf+env._motion_time_offsets).clone(),scope=scope,groups=groups)
        history=first['x'][:,None].repeat(1,3,1);xyhistory=first['xy'][:,None].repeat(1,3,1)
        bias=bias*scope[:,None];active=torch.ones(1024,device='cuda:0',dtype=torch.bool);failed=torch.zeros_like(active)
        total=torch.zeros(1024,device='cuda:0');discounted=total.clone();boot=total.clone();ticks=torch.zeros_like(total,dtype=torch.long)
        rng=torch.Generator(device='cuda:0').manual_seed(reset_seed+2000000)
        initial_hash=hashlib.sha256(obs.cpu().numpy().tobytes()).hexdigest()
        for tick in range(horizon):
            agent._decide_action(obs,info);dist=agent._model.eval_actor(agent._obs_norm.normalize(obs))
            raw=base.sample_normalized_action(dist,rng) if noisy else dist.mode
            nxt,reward,done,info=env.step(agent._a_norm.unnormalize(raw+residual_scale(tick)*bias))
            ended=done!=DoneFlags.NULL.value;fail=done==DoneFlags.FAIL.value
            assert torch.isfinite(reward).all();ticks+=active
            if audit:
                nx=ctx.physical(nxt);xy=env._engine.get_root_pos(env._get_char_id())[:,:2].clone()
                history=torch.cat((history[:,1:],nx[:,None]),1);xyhistory=torch.cat((xyhistory[:,1:],xy[:,None]),1)
                dense,_=scorer(history,xyhistory,motion,nxt[:,-2:],first['age']+tick+1,first['times']+(tick+1)/30.,pert)
                hard,_=scorer.failure(nx,xy,motion,first['age']+tick+1,pert)
                mask=active&scope
                if mask.any():score_error=max(score_error,float((dense-float(env._perturb_cfg['loco_failure_penalty'])*fail-reward)[mask].abs().max()))
                event_mismatch+=int(((hard!=fail)&mask).sum())
            value=agent._model.eval_critic(agent._obs_norm.normalize(nxt)).squeeze(-1)
            boot+=.99**(tick+1)*active*ended*(~fail)*value
            active,failed,total,discounted=accumulate(active,failed,total,discounted,reward,ended,fail,tick)
            obs,info=agent._reset_done_envs(done)
        assert score_error<.002 and event_mismatch==0,(score_error,event_mismatch)
        return discounted+boot+.99**horizon*active*value,pack(reset_seed,groups,motion,failed,total,ticks,initial_hash),first

    @torch.no_grad()
    def model_score(first,bias):
        nonlocal parity_done
        mask=first['scope'];x=first['x'][mask].clone();motion=first['motion'][mask];pert=first['pert'][mask];phase=first['phase'][mask].clone()
        h=x[:,None].repeat(1,3,1);xyh=first['xy'][mask,None].repeat(1,3,1);n=len(x)
        wm.begin(x.new_zeros(n,31,180));active=torch.ones(n,device=x.device,dtype=torch.bool)
        score=x.new_zeros(n);uncertainty=score.clone();bias=bias[mask]
        for tick in range(32):
            obs=ctx.obs(x,motion,phase);dist=agent._model.eval_actor(obs)
            action=(dist.mode+residual_scale(tick)*bias).clamp(ctx.low,ctx.high)
            age=first['age'][mask]+tick+1;times=first['times'][mask]+(tick+1)/30.
            phase=phase_feedback(agent._model.eval_phase(obs),ctx.clock_phase(motion,times),pert)
            if not parity_done:
                expected=RecurrentCorrection.step(wm,x,action)
                wm.begin(x.new_zeros(n,31,180));nx=wm.step(x,action)
                error=float((expected-nx).abs().max());assert error<1e-6,error
                report['recurrent_mean_parity_max_abs_error']=error;parity_done=True
            else:nx=wm.step(x,action)
            xy=xyh[:,-1]+(origin_velocity(ctx,x)[:,:2]+origin_velocity(ctx,nx)[:,:2])/60.
            h=torch.cat((h[:,1:],nx[:,None]),1);xyh=torch.cat((xyh[:,1:],xy[:,None]),1)
            dense,_=scorer(h,xyh,motion,phase,age,times,pert);fail,_=scorer.failure(nx,xy,motion,age,pert)
            score+=.99**tick*active*(dense-float(env._perturb_cfg['loco_failure_penalty'])*fail)
            uncertainty+=.99**tick*active*wm.uncertainty
            active&=~fail;x=nx
        score+=.99**32*active*agent._model.eval_critic(ctx.obs(x,motion,phase)).squeeze(-1)
        assert torch.isfinite(score).all() and torch.isfinite(uncertainty).all()
        return score,uncertainty

    def pool(reset_seed):
        rng=torch.Generator(device='cuda:0').manual_seed(reset_seed+3000000)
        return torch.cat((zero[None],(.075*torch.randn(15,1024,34,device='cuda:0',generator=rng)).clamp(-.225,.225)))

    emit('UNCERTAIN_READY',seed=seed,seconds=time.perf_counter()-start)
    shared=output.parent/'calibration.json'
    if calibration_owner:
        begun=time.perf_counter();biases=pool(849180);real=[];pred=[];us=[];native_seconds=0.;model_seconds=0.;native_durations=[]
        # Prime simulator caches with a separate seed before timed calibration.
        native(849179,zero,8)
        for i,bias in enumerate(biases):
            t=time.perf_counter();score,_,first=native(849180,bias,32,audit=i==0);duration=time.perf_counter()-t;native_seconds+=duration;native_durations.append(duration)
            t=time.perf_counter();s,u=model_score(first,bias);model_seconds+=time.perf_counter()-t
            real.append(score[first['scope']]);pred.append(s);us.append(u)
            emit('UNCERTAIN_CALIBRATION',candidate=i,native_seconds=native_seconds,model_seconds=model_seconds)
        real,pred,us=map(torch.stack,(real,pred,us));worlds=torch.arange(1024,device='cuda:0')[first['scope']]
        calibration=calibrate(pred,real,us,worlds%10!=0)
        calibration.update(seed=849180,native_seconds=native_seconds,model_seconds=model_seconds,seconds=time.perf_counter()-begun,
                           native_pool_seconds_excluding_audit_estimate=sum(native_durations[1:])/15*16,
                           model_sha256=digest,scorer_max_error=score_error,hard_event_mismatches=event_mismatch)
        torch.save(dict(real=real.cpu(),predicted=pred.cpu(),uncertainty=us.cpu(),worlds=worlds.cpu()),output/'calibration_scores.pt')
        base.write(shared,calibration);emit('UNCERTAIN_CALIBRATED',**calibration)
    else:
        deadline=time.perf_counter()+300
        while not shared.exists():
            if time.perf_counter()>deadline:raise TimeoutError('No calibration from paired worker')
            time.sleep(.25)
        calibration=json.loads(shared.read_text());assert calibration['model_sha256']==digest
    report['calibration']=calibration
    report['setup_and_calibration_wait_seconds']=time.perf_counter()-start
    _,_,first=native(seed,zero,8);biases=pool(seed);pred=[];us=[];planning=time.perf_counter()
    for bias in biases:
        s,u=model_score(first,bias);pred.append(s);us.append(u)
    pred,us=map(torch.stack,(pred,us));ids=torch.arange(len(pred[0]),device='cuda:0');selected={}
    for name,scores in [('raw',pred),('uncertain',pred-calibration['coefficient']*us)]:
        winner=scores.argmax(0);bias=zero.clone();bias[first['scope']]=biases[:,first['scope']][winner,ids]
        selected[name]=bias;report[name+'_zero_fraction']=float((winner==0).float().mean())
    report['planning_seconds']=time.perf_counter()-planning
    report['raw_uncertain_same_selection_fraction']=float((selected['raw'][first['scope']]==selected['uncertain'][first['scope']]).all(-1).float().mean())
    emit('UNCERTAIN_SELECTED',seed=seed,planning_seconds=report['planning_seconds'],coefficient=calibration['coefficient'])
    selected={'control':zero,**selected};report['selection_frozen_before_evaluation']=True
    for mode,noisy in [('deterministic',False),('noisy',True)]:
        report['evaluations'][mode]={}
        for name,bias in selected.items():
            _,ev,_=native(seed,bias,120,noisy=noisy)
            report['evaluations'][mode][name]=dict(rows=[ev])
            emit('UNCERTAIN_EVALUATED',seed=seed,mode=mode,arm=name,groups=ev['groups'])
            base.write(output/'result.json',report)
    report['policy_max_abs_delta']=max(float((v-agent.state_dict()[k]).abs().max()) for k,v in initial.items())
    report['world_max_abs_delta']=max(float((v-wm.state_dict()[k]).abs().max()) for k,v in original_world.items())
    assert report['policy_max_abs_delta']==report['world_max_abs_delta']==0
    report.update(complete=True,reset_max_abs_error=reset_error,total_seconds=time.perf_counter()-start)
    base.write(output/'result.json',report);emit('UNCERTAIN_COMPLETE',seed=seed,seconds=report['total_seconds'])


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ['root','checkpoint','output','source','model_file','seed']:p.add_argument('--'+key.replace('_','-'),required=True)
    p.add_argument('--calibration-owner',action='store_true');run(**vars(p.parse_args()))
