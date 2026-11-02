"""Compare dynamics priors on fixed real data before changing a policy."""
import copy,hashlib,json,time
import torch
from torch import nn
import supermimic_race as base
from supermimic_structured import GraphModelTrainer


def value_gradient_weights(gradient,training_mask):
    """Bounded VaGraM weights; one fixed global scale preserves loss magnitude.

    Source: pairlab/vagram, vaml_mlp.py; paper Appendix E. This adaptation uses
    our single frozen PPO state-value critic, not the paper's four SAC critics.
    Clipping/normalization statistics use training worlds only.
    """
    norm=gradient.norm(dim=-1)
    bound=torch.quantile(norm[training_mask],.95)
    clipped=gradient*(bound/norm.clamp_min(1e-12)).clamp_max(1.)[...,None]
    weights=clipped.square();scale=weights[training_mask].mean().clamp_min(1e-12)
    return weights/scale,dict(norm_clip_95=float(bound),normalization=float(scale))


def reachable_value_gradient(ctx,wm,x,motion,phase):
    """Differentiate value only through skeleton-consistent observations.

    Ambient derivatives on exact hinge constants are not attainable errors.
    FK also folds key-position sensitivity back into the actual joint pose.
    """
    projected=(wm.skeleton(x*wm.std+wm.mean)-wm.mean)/wm.std
    value=ctx.a._model.eval_critic(ctx.obs(projected,motion,phase)).sum()
    ambient=torch.autograd.grad(value,projected,retain_graph=True)[0]
    reachable=torch.autograd.grad(projected,x,grad_outputs=ambient)[0]
    return reachable.detach(),ambient.detach(),projected.detach()


def cache_value_weights(ctx,wm,buffer):
    started=time.perf_counter();b=buffer.data
    targets=b['next_x'].flatten(0,1);motion=b['motion'].flatten();phase=b['next_phase'].flatten(0,1)
    gradients=torch.empty_like(targets)
    constants=[13+6*j+k for j in wm.skeleton.hinges for k in [2,3,4,5]]
    energy=targets.new_zeros(4,dtype=torch.float64);projection_error=0.
    for start in range(0,len(targets),4096):
        stop=start+4096;x=targets[start:stop].detach().requires_grad_(True)
        gradient,ambient,projected=reachable_value_gradient(ctx,wm,x,motion[start:stop],phase[start:stop])
        gradients[start:stop]=gradient
        energy+=torch.stack((ambient.square().sum(),ambient[:,constants].square().sum(),
                             gradient.square().sum(),gradient[:,constants].square().sum())).double()
        projection_error=max(projection_error,float((projected-x.detach()).abs().max()))
    training=(torch.arange(len(targets),device=targets.device)%buffer.n)%10!=0
    weights,stats=value_gradient_weights(gradients,training)
    assert torch.isfinite(weights).all() and weights[training].mean()>.99
    b['value_weights']=weights.reshape_as(b['next_x'])
    stats.update(derivative='through_skeleton_projection',constant_coordinate_indices=constants,
                 ambient_constant_energy_fraction=float(energy[1]/energy[0].clamp_min(1e-12)),
                 reachable_constant_energy_fraction=float(energy[3]/energy[2].clamp_min(1e-12)),
                 projection_state_max_abs=projection_error)
    assert stats['reachable_constant_energy_fraction']==0.
    if projection_error>.01:raise RuntimeError('Skeleton projection changes recorded targets: '+str(projection_error))
    stats['seconds']=time.perf_counter()-started
    print('MODEL_AUDIT_VALUE_WEIGHTS',json.dumps(stats),flush=True)
    return stats


def fit_and_audit(env,agent,ctx,wm,buffer,collect,out,seconds,horizon,provenance):
    started=time.perf_counter()
    for p in agent.parameters():p.requires_grad_(False)
    policy_before=[p.detach().clone() for p in agent.parameters()]
    result=dict(kind='model_architecture_audit',complete=False,provenance=provenance,
                actor_updates=0,fit_budget_seconds=seconds,checks=[])
    shared=out.parent/'model-audit-shared-replay.pt'
    direction_pools=None
    if provenance['integrated_model'] or provenance.get('regularized_model',False) or provenance.get('value_weighted_model',False) or provenance.get('directional_supervision',False) or provenance.get('heading_equivariant_model',False) or provenance.get('increment_model',False):
        print('MODEL_AUDIT_WAIT_SHARED_DATA',flush=True)
        deadline=time.perf_counter()+120
        while not shared.exists():
            if time.perf_counter()>deadline:raise TimeoutError('Paired model data did not arrive')
            time.sleep(.25)
        saved=torch.load(shared,map_location=ctx.device,weights_only=True)
        assert saved['n']==buffer.n and saved['capacity']==buffer.capacity
        buffer.data=saved['data'];buffer.ptr=saved['ptr'];buffer.count=saved['count']
        if 'value_weight_stats' in saved:result['value_weight_stats']=saved['value_weight_stats']
        if 'direction_pools' in saved:
            direction_pools=saved['direction_pools'];result['direction_stats']=saved['direction_stats']
        print('MODEL_AUDIT_SHARED_DATA_LOADED',flush=True)
    else:
        print('MODEL_AUDIT_COLLECT',flush=True)
        collect(256)
        if provenance.get('value_model_audit',False):result['value_weight_stats']=cache_value_weights(ctx,wm,buffer)
        if provenance.get('direction_model_audit',False):
            from supermimic_derivatives import prepare_pairs
            direction_pools,result['direction_stats']=prepare_pairs(buffer)
        temporary=shared.with_suffix('.partial')
        shared_data=dict(data=buffer.data,n=buffer.n,capacity=buffer.capacity,ptr=buffer.ptr,count=buffer.count)
        if 'value_weight_stats' in result:shared_data['value_weight_stats']=result['value_weight_stats']
        if direction_pools is not None:shared_data.update(direction_pools=direction_pools,direction_stats=result['direction_stats'])
        torch.save(shared_data,temporary)
        temporary.replace(shared)
        print('MODEL_AUDIT_SHARED_DATA_SAVED',flush=True)
    result['collection_seconds']=time.perf_counter()-started
    result['dataset_sha256']={k:hashlib.sha256(buffer.data[k].cpu().numpy().tobytes()).hexdigest() for k in ['x','a','next_x']}
    if 'value_weights' in buffer.data:
        result['value_weights_sha256']=hashlib.sha256(buffer.data['value_weights'].cpu().numpy().tobytes()).hexdigest()
    if direction_pools is not None:
        from supermimic_derivatives import sample_pairs,pair_hashes,directional_loss
        result['direction_pairs_sha256']=pair_hashes(direction_pools)
    result['shared_dataset']=True
    result['transitions']=buffer.count*buffer.n
    if hasattr(wm,'calibrate'):
        calibration_start=time.perf_counter()
        result['normalization']=wm.calibrate(buffer)
        result['normalization']['seconds']=time.perf_counter()-calibration_start
        print('MODEL_AUDIT_NORMALIZATION',json.dumps(result['normalization']),flush=True)
    base.seed(581092)
    validation={n:buffer.sample(512,n,holdout=True) for n in [1,8]}
    if direction_pools is not None:
        for b in validation.values():b.update(sample_pairs(direction_pools['heldout'],512))
    optimizer=torch.optim.Adam(wm.parameters(),lr=2e-4)
    trainer=GraphModelTrainer(wm,optimizer,ctx)

    def check(steps,elapsed):
        record=dict(steps=steps,fit_seconds=elapsed)
        with torch.no_grad():
            for h,b in validation.items():
                _,metrics=base.model_loss(wm,b,ctx)
                record['h'+str(h)]={k:float(v) for k,v in metrics.items()}
            b=validation[1];predicted=wm.step(b['x'][0],b['a'][0])
            pa=ctx.policy(predicted,b['motion'][0],b['next_phase'][0])[0]
            ta=ctx.policy(b['next_x'][0],b['motion'][0],b['next_phase'][0])[0]
            record['next_action_rmse']=float((pa-ta).square().mean().sqrt())
            if direction_pools is not None:
                record['heldout_directional_change_mse']=float(directional_loss(wm,validation[1]))
                record['heldout_directional_target_mse']=float(validation[1]['direction_dy'].square().mean())
            for horizon,batch in validation.items():
                x=batch['x'][0];alive=torch.ones(len(x),device=x.device);error=0.;weight=0.
                for tick in range(horizon):
                    x=wm.step(x,batch['a'][tick])
                    pv=agent._model.eval_critic(ctx.obs(x,batch['motion'][tick],batch['next_phase'][tick])).flatten()
                    tv=agent._model.eval_critic(ctx.obs(batch['next_x'][tick],batch['motion'][tick],batch['next_phase'][tick])).flatten()
                    error+=((pv-tv).square()*alive).sum();weight+=alive.sum()
                    alive=alive*(~batch['done'][tick])
                record['h'+str(horizon)+'_critic_rmse']=float((error/weight.clamp_min(1)).sqrt())
        result['checks'].append(record);base.write(out/'result.json',result)
        print('MODEL_AUDIT_CHECK',json.dumps(record),flush=True)
        return record

    initial=check(0,0.)
    fit_start=time.perf_counter();steps=0;next_check=30.
    while time.perf_counter()-fit_start<seconds:
        batch=buffer.sample(256,8)
        if direction_pools is not None:batch.update(sample_pairs(direction_pools['train'],256))
        if steps==0:
            reference=copy.deepcopy(wm);reference_opt=torch.optim.Adam(reference.parameters(),lr=2e-4)
        trainer.step(batch)
        if steps<2:
            loss,_=base.model_loss(reference,batch,ctx);reference_opt.zero_grad(set_to_none=True)
            loss.backward();nn.utils.clip_grad_norm_(reference.parameters(),1.);reference_opt.step()
            difference=max(float((a-b).abs().max()) for a,b in zip(wm.parameters(),reference.parameters()))
            if difference>2e-5:raise RuntimeError('Captured fit differs from eager: '+str(difference))
            print('GRAPH_FIT_VERIFIED',steps,difference,flush=True)
            if steps==1:del reference,reference_opt
        steps+=1;elapsed=time.perf_counter()-fit_start
        if elapsed>=next_check:
            current=check(steps,elapsed);next_check+=30.
            if elapsed>=60 and current['h1']['state_nse']>=.95*initial['h1']['state_nse'] and current['next_action_rmse']>=initial['next_action_rmse']:
                result['early_stop']='No state-prediction improvement and next-action prediction regressed after 60 seconds'
                print('MODEL_AUDIT_EARLY_STOP',result['early_stop'],flush=True);break
    result['fit_seconds']=time.perf_counter()-fit_start
    final=check(steps,result['fit_seconds'])
    torch.save(dict(model=wm.state_dict(),integrated=provenance['integrated_model'],
                    regularized=provenance.get('regularized_model',False),
                    heading_equivariant=provenance.get('heading_equivariant_model',False),
                    increment_model=provenance.get('increment_model',False),
                    value_weighted=provenance.get('value_weighted_model',False),
                    value_add_mse=provenance.get('value_add_mse',False),
                    directional_supervision=provenance.get('directional_supervision',False)),out/'world_model.pt')
    if final['h1']['state_nse']<.05 and final['h1']['state_nse']<.8*final['h1']['identity_nse']:
        from supermimic_reward_audit import audit
        nested=out/'gradient';nested.mkdir(exist_ok=True)
        result['gradient_audit']=audit(env,agent,ctx,wm,nested,horizon)
    else:
        result['gradient_audit_skipped']='Insufficient held-out single-step accuracy'
    result['policy_parameter_delta_l2']=float(sum((p.detach()-q).square().sum() for p,q in zip(agent.parameters(),policy_before)).sqrt())
    assert result['policy_parameter_delta_l2']==0.
    result.update(complete=True,total_audit_seconds=time.perf_counter()-started)
    base.write(out/'result.json',result)
    print('MODEL_AUDIT_COMPLETE',json.dumps({k:v for k,v in result.items() if k not in ['provenance','checks','gradient_audit']}),flush=True)
    return result
