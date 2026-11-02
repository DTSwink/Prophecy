"""Frozen conditional multi-fidelity gradient screen, never a production learner.

MFPG-PPO (arxiv2610.02505) motivates paired simulator/model trajectories and
an independent model mean. Here every model copy has the SAME real start;
this sacrifices between-start variance reduction to avoid distribution bias.
No actor update or learning-speed claim. Projection covers the motor output
layer, not the entire actor. Separate heldout seeds validate a fitted coefficient.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import numpy as np
import torch
import supermimic_race as base
from supermimic_imagined_exact import origin_velocity, phase_feedback


def advantages(rewards, values, next_values, failures, ended, gamma=.99, lam=.98):
    """Pre-reset timeout bootstrap, zero failure bootstrap, no reset leakage."""
    result=[];future=torch.zeros_like(rewards[0])
    for t in reversed(range(len(rewards))):
        delta=rewards[t]+gamma*next_values[t]*(~failures[t])-values[t]
        future=delta+gamma*lam*(~ended[t])*future
        result.append(future)
    return torch.stack(result[::-1])


def fit_coefficient(high, corrector):
    """Minimize summed projected-gradient variance on calibration worlds only."""
    h=high-high.mean(0);c=corrector-corrector.mean(0)
    return float(-(h*c).sum()/c.square().sum().clamp_min(1e-12))


def variance_ratio(high, corrector, coefficient):
    h=high-high.mean(0);z=high+coefficient*corrector;z=z-z.mean(0)
    return float(z.square().sum()/h.square().sum().clamp_min(1e-12))


@torch.no_grad()
def features(ctx,x,motion,phase,epsilon,hidden_projection,action_projection):
    obs=ctx.obs(x,motion,phase)
    hidden=ctx.a._model._actor_layers(obs)
    dist=ctx.a._model._action_dist(hidden)
    hp=torch.cat((hidden,torch.ones_like(hidden[:,:1])),-1)@hidden_projection
    score=(epsilon/dist.stddev)@action_projection
    value=ctx.a._model.eval_critic(obs).squeeze(-1)
    return hp*score,value,dist


@torch.no_grad()
def branch_probe(ctx,wm,scorer,rows,group,branch,seed,hp,ap):
    """32-step paired trajectories + four independent copies; no refitting."""
    first=rows[branch];n=len(first['x']);copies=5
    def tile(v):return v.repeat((copies,)+(1,)*(v.ndim-1))
    motion=tile(first['motion']);pert=tile(first['pert'])
    x=tile(first['x']);phase=tile(first['phase'])
    history=tile(first['history']);xy_history=tile(first['history_xy'])
    age=tile(first['age']);times=tile(first['times'])
    alive=torch.ones(copies*n,device=x.device,dtype=torch.bool)
    real_alive=first['valid'].clone()
    rng=torch.Generator(device=x.device).manual_seed(seed+2000000+branch)
    predicted={k:[] for k in ['reward','value','next_value','fail','ended','gradient','active']}
    actual={k:[] for k in predicted}
    started=time.perf_counter()
    for t in range(32):
        real=rows[branch+t]
        epsilon=torch.cat((real['epsilon'],torch.randn(((copies-1)*n,34),device=x.device,generator=rng)))
        grad,value,dist=features(ctx,x,motion,phase,epsilon,hp,ap)
        executed=(dist.mode+dist.stddev*epsilon).clamp(ctx.low,ctx.high)
        age=age+1;times=times+1/30.
        next_phase=phase_feedback(ctx.a._model.eval_phase(ctx.obs(x,motion,phase)),ctx.clock_phase(motion,times),pert)
        nx=wm.step(x,executed)
        nx=torch.where(alive[:,None],nx,x)
        next_phase=torch.where(alive[:,None],next_phase,phase)
        xy=xy_history[:,-1]+alive[:,None]*(origin_velocity(ctx,x)[:,:2]+origin_velocity(ctx,nx)[:,:2])/60.
        history=torch.cat((history[:,1:],nx[:,None]),1)
        xy_history=torch.cat((xy_history[:,1:],xy[:,None]),1)
        dense,_=scorer(history,xy_history,motion,next_phase,age,times,pert)
        fail,_=scorer.failure(nx,xy,motion,age,pert)
        ended=fail|(age>=torch.where(pert,120.,300.))
        penalty=pert*(ctx.e._gaits[motion]!=-1)*float(ctx.e._perturb_cfg['loco_failure_penalty'])
        nv=ctx.a._model.eval_critic(ctx.obs(nx,motion,next_phase)).squeeze(-1)
        pg=dict(reward=dense-penalty*fail,value=value,next_value=nv,fail=fail,ended=ended,
                gradient=grad,active=alive.clone())
        for k,v in pg.items():predicted[k].append(v)
        alive &= ~ended
        rg,rv,_=features(ctx,real['x'],real['motion'],real['phase'],real['epsilon'],hp,ap)
        rnv=ctx.a._model.eval_critic(ctx.obs(real['next_x'],real['motion'],real['next_phase'])).squeeze(-1)
        rd=dict(reward=real['reward'],value=rv,next_value=rnv,fail=real['fail'],ended=real['ended'],
                gradient=rg,active=real_alive.clone())
        for k,v in rd.items():actual[k].append(v)
        real_alive &= ~real['ended'];x=nx;phase=next_phase
    torch.cuda.synchronize();seconds=time.perf_counter()-started
    selected=first['valid']&(group==2)
    result={}
    for horizon in [8,32]:
        gradients={};surrogates={}
        for name,data in [('real',actual),('model',predicted)]:
            d={k:torch.stack(v[:horizon]) for k,v in data.items()}
            adv=advantages(d['reward'],d['value'],d['next_value'],d['fail'],d['ended'])
            gradients[name]=(adv[...,None]*d['gradient']*d['active'][...,None]).sum(0)/horizon
            surrogates[name]=(adv*d['active']).sum(0)/horizon
        hg=gradients['real'][selected]
        lg=gradients['model'].reshape(copies,n,-1)[:,selected]
        scalar=surrogates['model'].reshape(copies,n)[:,selected]
        result[horizon]=dict(high=hg.cpu().numpy(),coupled=lg[0].cpu().numpy(),
             independent=lg[1:].mean(0).cpu().numpy(),high_scalar=surrogates['real'][selected].cpu().numpy(),
             low_scalar=scalar[0].cpu().numpy(),motion=first['motion'][selected].cpu().numpy())
        assert all(np.isfinite(v).all() for v in result[horizon].values())
    return result,seconds


def run(root,checkpoint,output,model_file,seed):
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
    from supermimic_rollout_calibration import capture
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6894);base.seed(seed)
    cfg,ec,ac=[yaml.safe_load((root/'prepared'/(n+'_config.yaml')).read_text()) for n in ['env','engine','agent']]
    env=PerturbedOmniEnv(cfg,ec,1024,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0')
    restore(agent,checkpoint)
    if cfg['perturbed_motion'].get('observation_normalization')=='physical_scales_v1':migrate_physical_observation_scales(agent)
    agent._init_train();agent.eval();initial={k:v.detach().clone() for k,v in agent.state_dict().items()}
    ctx=base.Context(env,agent);wm=IncrementWorld(ctx.mean,ctx.std,ctx.dim,env._kin_char_model,env._key_body_ids).cuda()
    wm.load_state_dict(torch.load(model_file,map_location='cuda:0',weights_only=True)['model']);wm.eval()
    assert int(wm.norm_count)>0
    original_world={k:v.detach().clone() for k,v in wm.state_dict().items()};scorer=ExactReward(ctx)
    rng=torch.Generator(device='cuda:0').manual_seed(947200)
    hp=torch.randint(2,(513,64),device='cuda:0',generator=rng).float()*2-1
    ap=torch.randint(2,(34,64),device='cuda:0',generator=rng).float()*2-1
    report=dict(kind='conditional_multifidelity_probe',complete=False,seed=seed,actor_updates=0,
       scope='Frozen motor output-layer gradient sketch only; no full-actor/learning claim. Perturbed locomotion only.',
       independent_model_copies=4,projection_dimensions=64,branches=[0,24,56,80],horizons=[8,32],
       exploration_std=.075,world_sha256=hashlib.sha256(Path(model_file).read_bytes()).hexdigest(),
       checkpoint_sha256=hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest(),known_prior_preparation_seconds=326.300587689,
       setup_seconds=time.perf_counter()-started,branches_report=[])
    print('MULTIFIDELITY_STARTED',json.dumps(report),flush=True)
    real_start=time.perf_counter();rows,group,validation=capture(ctx,scorer,seed,True)
    torch.cuda.synchronize();report['real_capture_120ticks_seconds']=time.perf_counter()-real_start
    report['native_scoring_validation']=validation
    with torch.no_grad():
        dist=agent._model.eval_actor(ctx.obs(rows[0]['x'],rows[0]['motion'],rows[0]['phase']))
        assert torch.allclose(dist.stddev,torch.full_like(dist.stddev,.075),atol=1e-6,rtol=0)
    arrays={}
    for branch in report['branches']:
        result,elapsed=branch_probe(ctx,wm,scorer,rows,group,branch,seed,hp,ap)
        entry=dict(branch=branch,paired_and_independent_model_seconds=elapsed,rows=len(result[32]['high']))
        for horizon,data in result.items():
            for name,value in data.items():arrays[f'b{branch}_h{horizon}_{name}']=value
        report['branches_report'].append(entry);base.write(output/'result.json',report)
        print('MULTIFIDELITY_PROGRESS',json.dumps(entry),flush=True)
    report['policy_max_abs_delta']=max(float((v-initial[k]).abs().max()) for k,v in agent.state_dict().items())
    report['world_max_abs_delta']=max(float((v-original_world[k]).abs().max()) for k,v in wm.state_dict().items())
    assert report['policy_max_abs_delta']==report['world_max_abs_delta']==0
    np.savez_compressed(output/'gradient_sketch.npz',**arrays)
    report.update(complete=True,total_worker_seconds=time.perf_counter()-started)
    base.write(output/'result.json',report);print('MULTIFIDELITY_COMPLETE',json.dumps(report),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ['root','checkpoint','output','model_file']:p.add_argument('--'+k.replace('_','-'),required=True)
    p.add_argument('--seed',type=int,required=True)
    run(**vars(p.parse_args()))
