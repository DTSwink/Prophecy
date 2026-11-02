"""Bounded, fixed-policy model fitting: paired batch sizes on identical fresh data."""
import copy
import hashlib
import json
import time

import torch
from torch import nn
from torch.nn import functional as F

import supermimic_race as base
from supermimic_structured import GraphModelTrainer


@torch.no_grad()
def forecast(ctx, wm, b, closed_loop):
    x=b['x'][0];phase=b['phase'][0];motion=b['motion'][0];pert=b['pert'][0]
    alive=torch.ones(len(x),device=x.device,dtype=torch.bool);result={}
    for tick in range(len(b['a'])):
        if closed_loop:
            obs=ctx.obs(x,motion,phase)
            mean=ctx.a._model.eval_actor(obs).mode
            if tick==0:
                error=float((mean-b['mean_a'][0]).abs().max())
                if error>2e-4:raise RuntimeError('Recorded policy means disagree: '+str(error))
            action=(mean+b['raw_a'][tick]-b['mean_a'][tick]).clamp(ctx.low,ctx.high)
            pred=ctx.a._model.eval_phase(obs)
            phase=torch.where(pert[:,None],F.normalize(pred,dim=-1,eps=1e-6),b['next_phase'][tick])
        else:
            action=b['a'][tick];phase=b['next_phase'][tick]
        x=wm.step(x,action)
        if tick+1 in (1,8,32):
            predicted=ctx.a._model.eval_actor(ctx.obs(x,motion,phase)).mode
            actual=ctx.a._model.eval_actor(ctx.obs(b['next_x'][tick],motion,b['next_phase'][tick])).mode
            scopes={'all':alive,'perturbed_loco':alive&pert&(ctx.e._gaits[motion]!=-1)}
            result['h'+str(tick+1)]={name:dict(rows=int(mask.sum()),
                state_nse=float((x-b['next_x'][tick])[mask].square().mean()),
                next_action_rmse=float((predicted-actual)[mask].square().mean().sqrt()))
                for name,mask in scopes.items()}
        alive=alive&~b['done'][tick]
    return result


def auxiliary_gradient_audit(ctx,wm,buffer):
    """Measure only transition parameters; head weights are distinct parameters."""
    assert not getattr(wm,'detach_auxiliary_inputs',False)
    parameters=list(wm.dynamics.parameters());records=[]
    for seed in [834763,834764,834765]:
        base.seed(seed);batch=buffer.sample(256,8)
        loss,metrics=base.model_loss(wm,batch,ctx)
        def gradient(value):
            return torch.cat([v.flatten() for v in torch.autograd.grad(value,parameters,retain_graph=True)])
        total=gradient(loss);reward=gradient(metrics['reward_mse']);terminal=gradient(.1*metrics['term_bce'])
        auxiliary=reward+terminal;state=total-auxiliary
        cosine=float(torch.nn.functional.cosine_similarity(state[None],total[None]))
        record=dict(seed=seed,state_gradient_norm=float(state.norm()),
            reward_gradient_norm=float(reward.norm()),terminal_gradient_norm=float(terminal.norm()),
            auxiliary_to_state_norm=float(auxiliary.norm()/state.norm().clamp_min(1e-12)),
            total_to_state_cosine=cosine)
        if not all(torch.isfinite(v).all() for v in [state,reward,terminal,total]):
            raise RuntimeError('Nonfinite model-gradient audit')
        records.append(record);print('FIT_DOSE_AUX_GRADIENT',json.dumps(record),flush=True)
    # Do not spend another fit on negligible aggregate interference.
    gate=any(r['auxiliary_to_state_norm']>=.05 or r['total_to_state_cosine']<.995 for r in records)
    return dict(records=records,fit_gate=gate,
        rule='Fit only if any auxiliary/state gradient norm >=5% or total/state cosine <0.995; otherwise diagnostic only.')


def run(agent,ctx,wm,buffer,collect,out,seconds,batch_size,provenance,head_fit_mode=None,capacity_width=0):
    started=time.perf_counter();assert batch_size in (256,2048)
    for p in agent.parameters():p.requires_grad_(False)
    policy_before=[p.detach().clone() for p in agent.parameters()]
    teacher=None
    if capacity_width:
        assert capacity_width in (1024,2048) and not head_fit_mode and batch_size==256
        if capacity_width==2048:
            from supermimic_capacity import widen_dynamics
            teacher=copy.deepcopy(wm.dynamics)
            wm.dynamics=widen_dynamics(wm.dynamics)
    world_before=[p.detach().clone() for p in wm.parameters()]
    result=dict(kind='model_fit_dose',complete=False,actor_updates=0,batch_size=batch_size,
        fit_window=8,fit_budget_seconds=seconds,checks=[],provenance=provenance,
        normalization='Frozen original training-only statistics',data_seed=84731)
    shared=out.parent/'fit-dose-shared-replay.pt'
    producer=(capacity_width==1024 if capacity_width else
              (head_fit_mode=='coupled') if head_fit_mode else batch_size==256)
    if producer:
        print('FIT_DOSE_COLLECT',flush=True);collect(256)
        temp=shared.with_suffix('.partial')
        torch.save(dict(data=buffer.data,n=buffer.n,capacity=buffer.capacity,
                        ptr=buffer.ptr,count=buffer.count),temp);temp.replace(shared)
    else:
        print('FIT_DOSE_WAIT_SHARED',flush=True);deadline=time.perf_counter()+150
        while not shared.exists():
            if time.perf_counter()>deadline:raise TimeoutError('Paired replay did not arrive')
            time.sleep(.25)
        saved=torch.load(shared,map_location=ctx.device,weights_only=True)
        assert saved['n']==buffer.n and saved['capacity']==buffer.capacity
        buffer.data=saved['data'];buffer.ptr=saved['ptr'];buffer.count=saved['count']
    result['collection_or_wait_seconds']=time.perf_counter()-started
    result['transitions']=buffer.count*buffer.n
    keys=['x','a','next_x','raw_a','mean_a','motion','phase','next_phase','done']
    result['dataset_sha256']={k:hashlib.sha256(buffer.data[k].cpu().numpy().tobytes()).hexdigest() for k in keys}
    base.seed(834762);validation=buffer.sample(512,32,holdout=True)
    result['validation_sha256']={k:hashlib.sha256(validation[k].cpu().numpy().tobytes()).hexdigest() for k in keys}
    if capacity_width:
        with torch.no_grad():
            raw=validation['x'][0]*wm.std+wm.mean
            features=(wm.features(raw,validation['a'][0])-wm.input_mean)/wm.input_std
            parity=float((teacher(features)-wm.dynamics(features)).abs().max()) if teacher is not None else 0.
        if parity>2e-5:raise RuntimeError('Widening changed initial normalized predictions: '+str(parity))
        result['capacity_audit']=dict(width=capacity_width,initial_prediction_max_abs=parity,
            dynamics_parameters=sum(p.numel() for p in wm.dynamics.parameters()),
            function_preserving=True,split_noise=.05 if teacher is not None else 0.)
        print('FIT_DOSE_CAPACITY',json.dumps(result['capacity_audit']),flush=True)
        del teacher
        base.seed(847310)
    if head_fit_mode:
        assert head_fit_mode in ('coupled','detached') and batch_size==256
        result['head_fit_mode']=head_fit_mode
        result['auxiliary_gradient_audit']=auxiliary_gradient_audit(ctx,wm,buffer)
        if not result['auxiliary_gradient_audit']['fit_gate']:
            result['skip_fit_reason']='Auxiliary influence below predeclared aggregate-gradient gate'
            seconds=0
        wm.detach_auxiliary_inputs=head_fit_mode=='detached'
        base.seed(847310)
    optimizer=torch.optim.Adam(wm.parameters(),lr=2e-4)
    trainer=GraphModelTrainer(wm,optimizer,ctx);steps=0;optimizer_seconds=0.

    def check(elapsed):
        record=dict(steps=steps,fit_seconds=elapsed,optimizer_seconds=optimizer_seconds,
            nominal_transition_predictions=steps*batch_size*8,
            replay_actions=forecast(ctx,wm,validation,False),
            policy_actions=forecast(ctx,wm,validation,True))
        result['checks'].append(record);base.write(out/'result.json',result)
        print('FIT_DOSE_CHECK',json.dumps(record),flush=True);return record

    initial=check(0.);fit_start=time.perf_counter();next_check=60.;regressions=0
    reference=copy.deepcopy(wm);reference_opt=torch.optim.Adam(reference.parameters(),lr=2e-4)
    while time.perf_counter()-fit_start<seconds:
        batch=buffer.sample(batch_size,8)
        step_start=time.perf_counter();trainer.step(batch);torch.cuda.synchronize()
        optimizer_seconds+=time.perf_counter()-step_start
        if steps<2:
            loss,_=base.model_loss(reference,batch,ctx);reference_opt.zero_grad(set_to_none=True)
            loss.backward();nn.utils.clip_grad_norm_(reference.parameters(),1.);reference_opt.step()
            difference=max(float((a-b).abs().max()) for a,b in zip(wm.parameters(),reference.parameters()))
            if difference>2e-5:raise RuntimeError('Captured fit differs from eager: '+str(difference))
            print('GRAPH_FIT_VERIFIED',steps,difference,flush=True)
            if steps==1:del reference,reference_opt
        steps+=1;elapsed=time.perf_counter()-fit_start
        if elapsed>=next_check:
            current=check(elapsed);next_check+=60.
            score=current['policy_actions']['h32']['perturbed_loco']
            old=initial['policy_actions']['h32']['perturbed_loco']
            bad=score['state_nse']>1.2*old['state_nse'] and score['next_action_rmse']>1.2*old['next_action_rmse']
            regressions=regressions+1 if bad else 0
            if regressions>=2:
                result['early_stop']='Closed-loop held-out forecasts regressed >20% at two successive checks'
                break
    result['fit_seconds']=time.perf_counter()-fit_start;check(result['fit_seconds'])
    torch.save(dict(model=wm.state_dict(),increment_model=True),out/'world_model.pt')
    result['world_model_sha256']=hashlib.sha256((out/'world_model.pt').read_bytes()).hexdigest()
    result['policy_parameter_delta_l2']=float(sum((p.detach()-q).square().sum() for p,q in zip(agent.parameters(),policy_before)).sqrt())
    result['world_model_parameter_delta_l2']=float(sum((p.detach()-q).square().sum() for p,q in zip(wm.parameters(),world_before)).sqrt())
    assert result['policy_parameter_delta_l2']==0
    assert result['world_model_parameter_delta_l2']>0 if seconds>0 else result['world_model_parameter_delta_l2']==0
    result.update(complete=True,total_audit_seconds=time.perf_counter()-started)
    base.write(out/'result.json',result)
    print('FIT_DOSE_COMPLETE',json.dumps({k:v for k,v in result.items() if k not in ['checks','provenance']}),flush=True)
    return result
