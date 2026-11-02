"""Short, self-stopping structured-world-model pilots; production is read-only."""
import argparse,copy,json,time,sys,os
from pathlib import Path
import numpy as np
import torch
from torch import nn
import supermimic_race as base
from supermimic_structured import StructuredWorld,GraphModelTrainer


def rates(evaluation):
    out={}
    for group in ['normal_loco','perturbed_loco']:
        g=[r['groups'][group] for r in evaluation['rows']]
        n=sum(v['rows'] for v in g)
        out[group]=100*sum(v['failures'] for v in g)/n
        out[group+'_return']=sum(v['mean_return']*v['rows'] for v in g)/n
    return out


def fit_real_critic(ctx,buffer,optimizer,target_model):
    """Eight-step targets from actual simulator transitions, with reset boundaries."""
    b=buffer.sample(128,8);shape=b['motion'].shape
    with torch.no_grad():
        obs=ctx.obs(b['x'].flatten(0,1),b['motion'].flatten(),b['phase'].flatten(0,1))
        nxt=ctx.obs(b['next_x'].flatten(0,1),b['motion'].flatten(),b['next_phase'].flatten(0,1))
        next_values=target_model.eval_critic(nxt).reshape(shape)
        start_value=target_model.eval_critic(obs[:shape[1]]).reshape(1,-1)
        penalty=b['pert']*(ctx.e._gaits[b['motion']]!=-1)*float(ctx.e._perturb_cfg['loco_failure_penalty'])
        reward=b['base_reward']-penalty*b['fail']
        timeout=b['done']&~b['fail']
        targets=base.lambda_targets(reward,(~b['done']).float(),timeout*next_values,
                                    torch.cat((start_value,next_values)),gamma=.99,lam=.98).flatten()
    params=list(ctx.a._model.get_critic_params())
    for _ in range(5):
        for ids in torch.randperm(len(targets),device=obs.device).chunk(4):
            pred=ctx.a._model.eval_critic(obs[ids]).squeeze(-1)
            loss=(pred-targets[ids]).square().mean();optimizer.zero_grad(set_to_none=True)
            loss.backward();norm=nn.utils.clip_grad_norm_(params,1.)
            if not torch.isfinite(norm):raise RuntimeError('Nonfinite real-data critic gradient')
            optimizer.step()
    with torch.no_grad():
        for target,current in zip(target_model.get_critic_params(),params):target.lerp_(current,.005)
    return float(loss.detach())


def run(root,checkpoint,out,horizon,seconds=240,actor_lr=1e-5,fast=False,warm_model=None,freeze_critic=False,gradient_audit=False,real_critic=False,native_ppo=False,stochastic_actor=False,noisy_eval=False,decoupled=False,reward_audit=False,exact_reward=False,critic_weight=1.,actor_batch=128,fresh_ticks=None,eval_interval=None,training_seed=57361,analytic_failure=False,freeze_world=False,stop_phase_gradient=False,model_audit=False,integrated_model=False,regularized_model=False,value_model_audit=False,value_weighted_model=False,value_add_mse=False,direction_model_audit=False,directional_supervision=False,objective_audit=False,advantage_clip=None,phase_stability=False,freeze_phase_predictor=False,imagined_exact=False,heading_model=False,hard_imagined_failure=False,increment_model=False,audit_context=False,critic_context=False,gradient_fidelity=False,fit_dose=0,head_fit_mode=None,capacity_width=0,direct_tracking_gradient=False,offpolicy_td3=False,offpolicy_bc_alpha=0.,native_awr=False,awr_replay_rollouts=1,actor_activation=None,evaluation_seeds=None):
    setup_started=time.perf_counter()
    root=Path(root).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    sys.path[:0]=[str(root/'pipeline'),str(root/'MimicKit/mimickit')];os.chdir(root/'MimicKit')
    os.environ['PYGLET_HEADLESS']='true';torch.set_num_threads(2)
    import warp as wp,yaml,mujoco_warp as mjw
    from util import mp_util
    from perturbed_omni import PerturbedOmniEnv
    from omni_policy import OmniPPOAgent
    from resume import restore,override_actor_learning_rate,migrate_physical_observation_scales
    from learning.base_agent import AgentMode
    from envs.base_env import DoneFlags
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6800+horizon)
    base.seed(training_seed)
    cfg,ec,ac=[yaml.safe_load((root/'prepared'/(n+'_config.yaml')).read_text()) for n in ['env','engine','agent']]
    env=PerturbedOmniEnv(cfg,ec,1024,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0')
    restored=restore(agent,checkpoint);override_actor_learning_rate(agent,1.125e-6)
    if cfg.get('perturbed_motion',{}).get('observation_normalization')=='physical_scales_v1':
        migrate_physical_observation_scales(agent)
    agent._init_train()
    activation_report=None
    if actor_activation is not None:
        from supermimic_smooth_actor import prepare
        assert imagined_exact and noisy_eval and evaluation_seeds is not None
        activation_report=prepare(env,agent,actor_activation,evaluation_seeds)
    context_install=None
    if critic_context:
        assert imagined_exact and critic_weight==1. and not native_ppo and not real_critic
        from supermimic_value_context import install,parameters
        context_install=install(agent._model)
        experiment_critic_params=parameters(agent._model)
        print('CRITIC_CONTEXT_INSTALLED',json.dumps(context_install),flush=True)
    else:experiment_critic_params=list(agent._model.get_critic_params())
    initial_actor=[p.detach().clone() for p in agent._model.get_actor_params()]
    initial_critic=[p.detach().clone() for p in experiment_critic_params]
    result=dict(kind='structured_pilot',horizon=horizon,actor_lr=actor_lr,complete=False,
                restored=restored,seconds_budget=seconds,updates=[],evaluations=[],stop_reason=None,
                freeze_critic=freeze_critic,real_critic_with_ema=real_critic,
                native_ppo=native_ppo,stochastic_imagination=stochastic_actor,decoupled=decoupled,
                noisy_evaluation=noisy_eval,training_seed=training_seed,exact_reward=exact_reward,critic_weight=critic_weight,
                actor_batch=actor_batch,fresh_ticks=fresh_ticks,eval_interval=eval_interval,analytic_failure=analytic_failure,freeze_world=freeze_world,stop_phase_gradient=stop_phase_gradient,
                checkpoint_sha256=base.hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest(),
                gpu=torch.cuda.get_device_name(),model_audit=model_audit,integrated_model=integrated_model,regularized_model=regularized_model,
                value_model_audit=value_model_audit,value_weighted_model=value_weighted_model,value_add_mse=value_add_mse,
                direction_model_audit=direction_model_audit,directional_supervision=directional_supervision)
    if advantage_clip is not None:
        assert native_ppo
        from supermimic_advantage import install
        result['advantage_clip_ablation']=install(agent,advantage_clip)
    if native_awr:
        assert native_ppo and advantage_clip is None and not phase_stability
        from supermimic_awr import install as install_awr
        result['native_awr']=install_awr(agent,replay_rollouts=awr_replay_rollouts)
        print('NATIVE_AWR_INSTALLED',json.dumps(result['native_awr']),flush=True)
    phase_probe=None
    if phase_stability:
        assert native_ppo
        from supermimic_phase_stability import install
        predictor,phase_probe=install(agent,freeze_phase_predictor)
        torch.save(predictor.state_dict(),out/'initial_phase_predictor.pt')
        result['phase_stability']=dict(freeze_perturbed=freeze_phase_predictor,authored_clock=False,
            normal_phase_supervision_unchanged=True,actor_motor_interface_unchanged=True)
    else:assert not freeze_phase_predictor
    assert not agent._need_normalizer_update()
    if decoupled:assert real_critic and not native_ppo
    if exact_reward:assert decoupled or imagined_exact
    if imagined_exact:assert exact_reward and not decoupled and not real_critic and not native_ppo
    if direct_tracking_gradient:assert imagined_exact and hard_imagined_failure
    result['actor_activation']=activation_report
    result['direct_tracking_gradient']=direct_tracking_gradient
    result['fully_imagined_exact_reward']=imagined_exact
    result['heading_equivariant_model']=heading_model
    result['increment_model']=increment_model
    result['audit_context']=audit_context
    result['critic_task_context']=context_install
    result['hard_imagined_failure']=hard_imagined_failure
    if hard_imagined_failure:assert imagined_exact
    check_seeds=[481031] if fast and not noisy_eval else [481031,481032]
    if evaluation_seeds is not None:check_seeds=list(evaluation_seeds)
    check_ticks=120 if fast else 300
    result['quick_check_ticks']=check_ticks
    baseline={'perturbed_loco':float('inf')}
    if not (gradient_audit or reward_audit or model_audit or objective_audit or gradient_fidelity or fit_dose):
        initial=dict(training_seconds=0.,rows=base.evaluate(env,agent,check_seeds,max_ticks=check_ticks))
        result['evaluations'].append(initial);baseline=rates(initial)
        print('BASELINE',json.dumps(baseline),flush=True)
        if noisy_eval:
            initial_noise=dict(training_seconds=0.,rows=base.evaluate(env,agent,check_seeds,max_ticks=check_ticks,exploration=True))
            result['noisy_evaluations']=[initial_noise];noise_baseline=rates(initial_noise)
            print('BASELINE_NOISY',json.dumps(noise_baseline),flush=True)
    if activation_report is not None:
        from supermimic_smooth_actor import verify_start
        verify_start(activation_report,dict(deterministic=initial,noisy=initial_noise))
    ctx=base.Context(env,agent)
    if offpolicy_td3:
        assert not (native_ppo or warm_model or imagined_exact or model_audit) and noisy_eval
        from supermimic_offpolicy import run as run_offpolicy
        return run_offpolicy(ctx,result,out,seconds,setup_started,training_seed,actor_lr,eval_interval or 180,offpolicy_bc_alpha)
    wm=StructuredWorld(ctx.mean,ctx.std,ctx.dim,env._kin_char_model,env._key_body_ids).cuda()
    assert sum([integrated_model,regularized_model,value_weighted_model,directional_supervision,heading_model,increment_model])<=1, 'Test model changes separately'
    if directional_supervision:assert direction_model_audit and model_audit
    if direction_model_audit:assert model_audit and not value_model_audit
    if value_weighted_model:assert value_model_audit and model_audit
    if value_add_mse:assert value_weighted_model
    if value_model_audit:assert model_audit
    if increment_model:
        assert (model_audit and not warm_model) or (imagined_exact and warm_model=='increments-audited')
        from supermimic_increments import IncrementWorld
        base.seed(573612)
        wm=IncrementWorld(ctx.mean,ctx.std,ctx.dim,env._kin_char_model,env._key_body_ids).cuda()
    elif heading_model:
        assert (model_audit and not warm_model) or (imagined_exact and warm_model=='heading-paired')
        from supermimic_equivariant import EquivariantWorld
        base.seed(573612)
        wm=EquivariantWorld(ctx.mean,ctx.std,ctx.dim,env._kin_char_model,env._key_body_ids).cuda()
    elif regularized_model:
        assert not warm_model, 'A regularized model must be fitted in its own parameterization'
        from supermimic_structured import RegularizedWorld
        base.seed(573612)
        wm=RegularizedWorld(ctx.mean,ctx.std,ctx.dim,env._kin_char_model,env._key_body_ids).cuda()
    elif integrated_model:
        assert not warm_model, 'An integrated model must be fitted in its own parameterization'
        from supermimic_structured import IntegratedWorld
        # Reset only model initialization so the paired audit starts with the
        # identical MLP parameters. Collection RNG is reset independently below.
        base.seed(573612)
        wm=IntegratedWorld(ctx.mean,ctx.std,ctx.dim,env._kin_char_model,env._key_body_ids,
                           env._velocity_mapping,env._body_com.reshape(-1,15,3)[0,0]).cuda()
    elif model_audit:
        base.seed(573612)
        wm=StructuredWorld(ctx.mean,ctx.std,ctx.dim,env._kin_char_model,env._key_body_ids).cuda()
    wm._audit_context_enabled=audit_context
    wm.value_weighted=value_weighted_model
    wm.value_add_mse=value_add_mse
    wm.directional_supervision=directional_supervision
    if warm_model and not native_ppo:
        if warm_model=='increments-audited':
            assert increment_model
            warm_model=str(next(Path('/kaggle/input').rglob('increments-audited-world.pt')))
            prior=json.loads((Path(warm_model).parent/'increment-model-provenance.json').read_text())
            assert base.hashlib.sha256(Path(warm_model).read_bytes()).hexdigest()==prior['sha256']
            result['model_pretraining_accounting']=prior
        if warm_model in ('heading-paired','residual-paired'):
            model_name='heading' if warm_model=='heading-paired' else 'residual'
            assert heading_model==(model_name=='heading')
            warm_model=str(next(Path('/kaggle/input').rglob(model_name+'-paired-world.pt')))
            prior=json.loads((Path(warm_model).parent/'heading-pair-provenance.json').read_text())
            assert base.hashlib.sha256(Path(warm_model).read_bytes()).hexdigest()==prior['models'][model_name]['sha256']
            result['model_pretraining_accounting']=prior['models'][model_name]
        if warm_model=='directional':
            warm_model=str(next(Path('/kaggle/input').rglob('directional-world-model.pt')))
            prior=json.loads((Path(warm_model).parent/'directional-model-provenance.json').read_text())
            assert base.hashlib.sha256(Path(warm_model).read_bytes()).hexdigest()==prior['sha256']
            result['model_pretraining_accounting']=prior
        if warm_model=='auto':warm_model=str(next(Path('/kaggle/input').rglob('h8/world_model.pt')))
        elif warm_model=='fast-h4':warm_model=str(next(Path('/kaggle/input').rglob('h4/world_model.pt')))
        elif warm_model=='cautious':warm_model=str(next(Path('/kaggle/input').rglob('small_step/world_model.pt')))
        wm.load_state_dict(torch.load(warm_model,map_location='cuda:0',weights_only=True)['model'])
        if increment_model:assert int(wm.norm_count)>0, 'Increment normalizers must be calibrated before imagination'
        result['warm_model']=dict(path=warm_model,sha256=base.hashlib.sha256(Path(warm_model).read_bytes()).hexdigest(),
            accounting='Reuses preceding pilot model fitting; this is a diagnostic, not a fresh wall-clock race')
        print('WARM_MODEL',json.dumps(result['warm_model']),flush=True)
    if gradient_fidelity:
        assert exact_reward and imagined_exact and increment_model and not critic_context
        from supermimic_gradient_fidelity import audit
        base.write(out/'provenance.json',result)
        return audit(env,agent,ctx,wm,out,horizon,exploration=noisy_eval,seconds=seconds)
    if objective_audit:
        from supermimic_objective_audit import audit
        base.write(out/'provenance.json',result)
        return audit(env,agent,ctx,wm,out,horizon,exploration=noisy_eval,seconds=seconds)
    if gradient_audit:
        from supermimic_gradient_audit import audit
        base.write(out/'provenance.json',result)
        return audit(env,agent,ctx,wm,out,horizon)
    if reward_audit:
        from supermimic_reward_audit import audit
        base.write(out/'provenance.json',result)
        return audit(env,agent,ctx,wm,out,horizon)
    if exact_reward:
        from supermimic_exact_reward import ExactReward
        exact_scorer=ExactReward(ctx)
    else:exact_scorer=None
    buffer=base.Replay(1024,'cuda:0');opt_wm=torch.optim.Adam(wm.parameters(),lr=2e-4)
    initial_world=[p.detach().clone() for p in wm.parameters()]
    trainer=GraphModelTrainer(wm,opt_wm,ctx) if fast and not native_ppo and not freeze_world else None
    actor_opt=torch.optim.Adam(agent._model.get_actor_params(),lr=actor_lr,betas=(.9,.95))
    critic_opt=torch.optim.Adam(experiment_critic_params,lr=2e-4)
    target_model=copy.deepcopy(agent._model) if real_critic else None
    if target_model is not None:
        for p in target_model.parameters():p.requires_grad_(False)
    model_steps=0;sim_steps=0;accepted=0;first_actor=None;updates=0;gate=False
    def reset_training():
        agent.set_mode(AgentMode.TRAIN);agent.train()
        mjw.reset_data(env._engine._solver.mjw_model,env._engine._solver.mjw_data)
        agent._curr_obs,agent._curr_info=agent._reset_envs()
        return ctx.physical(agent._curr_obs)[:,None].repeat(1,3,1)
    base.seed(training_seed);history=reset_training()
    history_xy=env._engine.get_root_pos(env._get_char_id())[:,None,:2].repeat(1,3,1)
    if noisy_eval:assert agent._get_exp_prob()==1., 'Noisy evaluation expects full production exploration'
    with torch.no_grad():
        result['exploration_std']=agent._model.eval_actor(agent._obs_norm.normalize(agent._curr_obs)).stddev[0].cpu().tolist()
    # Fail before learning if our skeleton projection changes valid simulator observations.
    with torch.no_grad():
        raw=agent._curr_obs[:,:146];projection_error=float((wm.skeleton(raw)-raw).abs().max())
    result['valid_state_projection_max_error']=projection_error
    if projection_error>2e-4:raise RuntimeError('Skeleton projection differs from simulator: '+str(projection_error))
    print('SKELETON_OK',projection_error,'hinges',wm.skeleton.hinges,flush=True)
    result['setup_and_baseline_seconds']=time.perf_counter()-setup_started
    started=time.perf_counter();next_eval=eval_interval or 60.;next_progress=0.;next_write=0.;held={};evaluation_seconds=0.
    next_actor_check=float('inf') if eval_interval else 10;best_rate=baseline['perturbed_loco'];best_at=None
    def collect(ticks):
        nonlocal history,history_xy,sim_steps
        with torch.no_grad():
            for _ in range(ticks):
                obs=agent._curr_obs;x=ctx.physical(obs);motion=env._motion_ids.clone()
                phase=obs[:,-2:].clone();age=torch.round(env._time_buf*30).clone()
                pert=env._perturbed_rows.clone();times=(env._time_buf+env._motion_time_offsets).clone()
                action,_=agent._decide_action(obs,agent._curr_info)
                extra={}
                if decoupled or fit_dose:
                    extra=dict(raw_a=agent._a_norm.normalize(action),
                               mean_a=agent._model.eval_actor(agent._obs_norm.normalize(obs)).mode)
                executed=agent._a_norm.normalize(action.clamp(env._action_bound_low,env._action_bound_high))
                nxt,reward,done,info=env.step(action);nx=ctx.physical(nxt)
                if exact_reward:
                    xy=env._engine.get_root_pos(env._get_char_id())[:,:2].clone()
                    extra.update(history_xy=history_xy,next_xy=xy)
                if analytic_failure:
                    com_vel=env._engine.get_body_vel(env._get_char_id())[:,env._com2_ids,:2]
                    extra['com2']=(com_vel*env._com2_masses[:,None]).sum(1).clone()
                fail=done==DoneFlags.FAIL.value;ended=done!=DoneFlags.NULL.value
                penalty=pert*(env._gaits[motion]!=-1)*float(env._perturb_cfg['loco_failure_penalty'])
                buffer.add(x=x,next_x=nx,a=executed,motion=motion,phase=phase,next_phase=nxt[:,-2:],
                    age=age,pert=pert,times=times,base_reward=reward+fail*penalty,fail=fail,done=ended,history=history,**extra)
                history=torch.cat((history[:,1:],nx[:,None]),1)
                if exact_reward:history_xy=torch.cat((history_xy[:,1:],xy[:,None]),1)
                agent._curr_obs,agent._curr_info=agent._reset_done_envs(done)
                rx=ctx.physical(agent._curr_obs);history[ended]=rx[ended,None].repeat(1,3,1);sim_steps+=1024
                if exact_reward:history_xy[ended]=env._engine.get_root_pos(env._get_char_id())[ended,None,:2].repeat(1,3,1)
    if fit_dose:
        assert increment_model and warm_model and not native_ppo and training_seed==84731
        from supermimic_fit_dose import run as fit_model
        return fit_model(agent,ctx,wm,buffer,collect,out,seconds,fit_dose,result,head_fit_mode,capacity_width)
    if model_audit:
        assert not warm_model and not native_ppo
        from supermimic_model_audit import fit_and_audit
        return fit_and_audit(env,agent,ctx,wm,buffer,collect,out,seconds,horizon,result)
    while time.perf_counter()-started<seconds:
        if native_ppo:
            agent._iter=updates
            metrics={k:float(v) for k,v in agent._train_iter().items()}
            if advantage_clip is not None:
                metrics.update({'advantage_audit_'+k:v for k,v in agent._advantage_audit.items()})
            if phase_probe is not None:
                metrics.update({'phase_stability_'+k:v for k,v in phase_probe().items()})
            if native_awr:
                metrics.update({'awr_audit_'+k:v for k,v in agent._awr_audit.items()})
            agent._sample_count=agent._update_sample_count();sim_steps+=1024*32;accepted+=1
            if first_actor is None:first_actor=time.perf_counter()-started
        else:
            metrics,model_steps,gate,held,accepted,first_actor = model_iteration(collect,buffer,trainer,wm,opt_wm,ctx,fast,model_steps,gate,held,warm_model,horizon,real_critic,critic_opt,target_model,actor_opt,freeze_critic,stochastic_actor,accepted,first_actor,started,decoupled,exact_scorer,critic_weight,actor_batch,fresh_ticks,analytic_failure,freeze_world,stop_phase_gradient,imagined_exact,hard_imagined_failure,direct_tracking_gradient)
        updates+=1;elapsed=time.perf_counter()-started
        row=dict(update=updates,seconds=elapsed,transitions=sim_steps,model_steps=model_steps,
                 accepted_actor_updates=accepted,gate=gate,metrics=metrics)
        result['updates'].append(row)
        if elapsed>=next_progress:
            print('PROGRESS',json.dumps(row),flush=True);next_progress=elapsed+15
        if elapsed>=next_write:
            base.write(out/'result.json',result);next_write=elapsed+15
        if elapsed<seconds and (elapsed>=next_eval or accepted>=next_actor_check):
            check_started=time.perf_counter()
            if not native_ppo:
                buffer.data['done'][(buffer.ptr-1)%buffer.capacity].fill_(True)
            rng=(torch.get_rng_state(),torch.cuda.get_rng_state(),np.random.get_state(),base.random.getstate())
            evaluation=dict(training_seconds=elapsed,rows=base.evaluate(env,agent,check_seeds,max_ticks=check_ticks))
            result['evaluations'].append(evaluation);score=rates(evaluation)
            print('EVALUATION',json.dumps(dict(seconds=elapsed,accepted=accepted,**score)),flush=True)
            if score['perturbed_loco']<best_rate and score['normal_loco']<=baseline['normal_loco']+1:
                best_rate=score['perturbed_loco'];best_at=elapsed
                torch.save({k:v.detach().cpu() for k,v in agent.state_dict().items()},out/'policy_best.pt')
            bad=(score['perturbed_loco']>baseline['perturbed_loco']+3 or score['normal_loco']>baseline['normal_loco']+2)
            if noisy_eval:
                noisy=dict(training_seconds=elapsed,rows=base.evaluate(env,agent,check_seeds,max_ticks=check_ticks,exploration=True))
                result['noisy_evaluations'].append(noisy);noise_score=rates(noisy)
                print('EVALUATION_NOISY',json.dumps(dict(seconds=elapsed,accepted=accepted,**noise_score)),flush=True)
                bad |= (noise_score['perturbed_loco']>noise_baseline['perturbed_loco']+5 or noise_score['normal_loco']>noise_baseline['normal_loco']+5)
            torch.set_rng_state(rng[0]);torch.cuda.set_rng_state(rng[1]);np.random.set_state(rng[2]);base.random.setstate(rng[3])
            history=reset_training();next_eval=(next_eval+eval_interval) if eval_interval else time.perf_counter()-started+45
            history_xy=env._engine.get_root_pos(env._get_char_id())[:,None,:2].repeat(1,3,1)
            next_actor_check=float('inf') if eval_interval else accepted+30;evaluation_seconds+=time.perf_counter()-check_started
            if bad:
                result['stop_reason']='Real-simulator regression exceeded the short-test threshold';break
    result['training_seconds']=time.perf_counter()-started
    result['intermediate_evaluation_seconds']=evaluation_seconds
    result['learning_seconds_excluding_checks']=result['training_seconds']-evaluation_seconds
    result['accepted_actor_updates']=accepted;result['first_actor_seconds']=first_actor
    result['best_quick_failure_percent']=best_rate;result['best_quick_seconds']=best_at
    result['final_heldout']=held
    if not native_ppo:
        result['world_model_parameter_delta_l2']=float(sum((p.detach()-q).square().sum() for p,q in zip(wm.parameters(),initial_world)).sqrt())
        if freeze_world:assert result['world_model_parameter_delta_l2']==0.
        torch.save(dict(model=wm.state_dict()),out/'world_model.pt')
    final_seeds=([481031,481032] if noisy_eval or (accepted and not result['stop_reason']) else [481031]) if fast else [481031,481032,481033,481034]
    if evaluation_seeds is not None:final_seeds=list(evaluation_seeds)
    final_ticks=check_ticks if noisy_eval else (300 if not fast or (accepted and not result['stop_reason']) else check_ticks)
    result['final_evaluation_ticks']=final_ticks
    final_started=time.perf_counter()
    final=dict(training_seconds=result['training_seconds'],rows=base.evaluate(env,agent,final_seeds,max_ticks=final_ticks))
    result['evaluations'].append(final);result['final_rates']=rates(final)
    if noisy_eval:
        noisy=dict(training_seconds=result['training_seconds'],rows=base.evaluate(env,agent,final_seeds,max_ticks=final_ticks,exploration=True))
        result['noisy_evaluations'].append(noisy);result['final_noisy_rates']=rates(noisy)
    if phase_probe is not None:result['final_phase_stability']=phase_probe()
    result['complete']=True
    result['final_evaluation_seconds']=time.perf_counter()-final_started
    result['total_worker_seconds']=time.perf_counter()-setup_started
    if hasattr(wm,'_critic_context_audit'):result['critic_context_audit']=wm._critic_context_audit
    result['actor_parameter_delta_l2']=float(sum((p.detach()-q).square().sum() for p,q in zip(agent._model.get_actor_params(),initial_actor)).sqrt())
    result['critic_parameter_delta_l2']=float(sum((p.detach()-q).square().sum() for p,q in zip(experiment_critic_params,initial_critic)).sqrt())
    if critic_context:
        result['critic_context_weight_l2']=float(agent._model._loco_critic_context.weight.detach().norm())
        assert result['critic_context_weight_l2']>0, 'Context projection never learned'
    torch.save({k:v.detach().cpu() for k,v in agent.state_dict().items()},out/'policy_final.pt')
    base.write(out/'result.json',result)
    print('PILOT_COMPLETE',json.dumps({k:v for k,v in result.items() if k not in ['updates','evaluations','noisy_evaluations','restored']}),flush=True)


def model_iteration(collect,buffer,trainer,wm,opt_wm,ctx,fast,model_steps,gate,held,warm_model,horizon,real_critic,critic_opt,target_model,actor_opt,freeze_critic,stochastic_actor,accepted,first_actor,started,decoupled=False,exact_scorer=None,critic_weight=1.,actor_batch=128,fresh_ticks=None,analytic_failure=False,freeze_world=False,stop_phase_gradient=False,imagined_exact=False,hard_imagined_failure=False,direct_tracking_gradient=False):
        agent=ctx.a
        collect(64 if buffer.count==0 else ((fresh_ticks or horizon) if decoupled else 3))
        metrics={}
        for _ in range(0 if freeze_world else (10 if fast else 5)):
            batch=buffer.sample(256,8)
            if trainer:
                if model_steps==0:
                    # Compare the captured update with ordinary eager Adam on
                    # two different batches before relying on its speed.
                    reference=copy.deepcopy(wm);reference_opt=torch.optim.Adam(reference.parameters(),lr=2e-4)
                loss,metrics=trainer.step(batch)
                if model_steps<2:
                    rl,_=base.model_loss(reference,batch,ctx);reference_opt.zero_grad(set_to_none=True)
                    rl.backward();nn.utils.clip_grad_norm_(reference.parameters(),1.);reference_opt.step()
                    difference=max(float((a-b).abs().max()) for a,b in zip(wm.parameters(),reference.parameters()))
                    if difference>2e-5:raise RuntimeError('Captured model fit differs from eager: '+str(difference))
                    print('GRAPH_FIT_VERIFIED',model_steps,difference,flush=True)
                    if model_steps==1:del reference,reference_opt
            else:
                loss,metrics=base.model_loss(wm,batch,ctx)
                opt_wm.zero_grad(set_to_none=True);loss.backward();gn=nn.utils.clip_grad_norm_(wm.parameters(),1.)
                if not torch.isfinite(gn):raise RuntimeError('Nonfinite world-model gradient')
                opt_wm.step()
            model_steps+=1
        metrics={k:float(v.detach()) for k,v in metrics.items()}
        if freeze_world or model_steps%50==0:
            with torch.no_grad():
                b=buffer.sample(256,1 if decoupled else horizon,holdout=True)
                _,held=base.model_loss(wm,b,ctx);held={k:float(v) for k,v in held.items()}
                predicted=wm.step(b['x'][0],b['a'][0])
                pa=ctx.policy(predicted,b['motion'][0],b['next_phase'][0])[0]
                ta=ctx.policy(b['next_x'][0],b['motion'][0],b['next_phase'][0])[0]
                held['next_action_rmse']=float((pa-ta).square().mean().sqrt())
            gate=(freeze_world or model_steps>=(50 if warm_model else 500)) and held['state_nse']<.05 and held['state_nse']<held['identity_nse']*.8 and (exact_scorer is not None or held['reward_mse']<.02)
            metrics['heldout']=held
        if gate and imagined_exact and not hasattr(wm,'_exact_score_validated'):
            from supermimic_imagined_exact import validate_real_reward
            validation=validate_real_reward(ctx,buffer,exact_scorer,hard_failure=hard_imagined_failure)
            wm._exact_score_validated=True
            if direct_tracking_gradient:
                wm._direct_tracking_scale=validation['reciprocal_derivative_median']
            if getattr(wm,'_audit_context_enabled',False):
                from supermimic_critic_context import audit as audit_critic_context
                with torch.random.fork_rng(devices=[torch.cuda.current_device()]):
                    wm._critic_context_audit=audit_critic_context(ctx,buffer,exact_scorer)
                print('CRITIC_CONTEXT_AUDIT',json.dumps(wm._critic_context_audit),flush=True)
            print('IMAGINED_SCORE_VERIFIED',json.dumps(validation),flush=True)
        if gate:
            real_critic_loss=fit_real_critic(ctx,buffer,critic_opt,target_model) if real_critic and critic_weight else None
            if imagined_exact:
                from supermimic_imagined_exact import update as fully_imagined_update
                update=fully_imagined_update(wm,buffer,ctx,actor_opt,critic_opt,exact_scorer,batch=actor_batch,horizon=horizon,hard_failure=hard_imagined_failure,critic_weight=critic_weight,stochastic_actor=stochastic_actor,stop_phase_gradient=stop_phase_gradient,direct_tracking_gradient=direct_tracking_gradient)
            elif decoupled:
                from supermimic_decoupled import update as decoupled_update
                update=decoupled_update(wm,buffer,ctx,actor_opt,target_model,horizon,batch=actor_batch,exact_reward=exact_scorer,critic_weight=critic_weight,fresh_ticks=fresh_ticks,analytic_failure=analytic_failure,stop_phase_gradient=stop_phase_gradient)
            else:
                update=base.imagined_update(wm,buffer,ctx,actor_opt,critic_opt,batch=128,horizon=horizon,
                                           update_critic=not (freeze_critic or real_critic),value_model=target_model,sample_actions=stochastic_actor)
            metrics.update(update)
            if real_critic:metrics['real_critic_loss']=real_critic_loss
            accepted+=not update['rejected']
            if first_actor is None:first_actor=time.perf_counter()-started
        return metrics,model_steps,gate,held,accepted,first_actor


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--checkpoint',required=True)
    p.add_argument('--output',required=True);p.add_argument('--horizon',type=int,required=True)
    p.add_argument('--seconds',type=float,default=240);p.add_argument('--actor-lr',type=float,default=1e-5)
    p.add_argument('--fast',action='store_true');p.add_argument('--warm-model');p.add_argument('--freeze-critic',action='store_true')
    p.add_argument('--gradient-audit',action='store_true')
    p.add_argument('--real-critic',action='store_true')
    p.add_argument('--native-ppo',action='store_true');p.add_argument('--stochastic-actor',action='store_true');p.add_argument('--noisy-eval',action='store_true')
    p.add_argument('--decoupled',action='store_true')
    p.add_argument('--reward-audit',action='store_true')
    p.add_argument('--heading-model',action='store_true')
    p.add_argument('--increment-model',action='store_true')
    p.add_argument('--audit-context',action='store_true')
    p.add_argument('--critic-context',action='store_true')
    p.add_argument('--gradient-fidelity',action='store_true')
    p.add_argument('--fit-dose',type=int,choices=[256,2048],default=0)
    p.add_argument('--head-fit-mode',choices=['coupled','detached'])
    p.add_argument('--capacity-width',type=int,choices=[1024,2048],default=0)
    p.add_argument('--direct-tracking-gradient',action='store_true')
    p.add_argument('--native-awr',action='store_true')
    p.add_argument('--awr-replay-rollouts',type=int,choices=[1,4],default=1)
    p.add_argument('--offpolicy-td3',action='store_true')
    p.add_argument('--offpolicy-bc-alpha',type=float,default=0.)
    p.add_argument('--hard-imagined-failure',action='store_true')
    p.add_argument('--imagined-exact',action='store_true')
    p.add_argument('--exact-reward',action='store_true');p.add_argument('--critic-weight',type=float,default=1.)
    p.add_argument('--actor-batch',type=int,default=128);p.add_argument('--fresh-ticks',type=int)
    p.add_argument('--eval-interval',type=float);p.add_argument('--training-seed',type=int,default=57361)
    p.add_argument('--analytic-failure',action='store_true');p.add_argument('--freeze-world',action='store_true')
    p.add_argument('--stop-phase-gradient',action='store_true')
    p.add_argument('--model-audit',action='store_true');p.add_argument('--integrated-model',action='store_true')
    p.add_argument('--regularized-model',action='store_true')
    p.add_argument('--value-model-audit',action='store_true');p.add_argument('--value-weighted-model',action='store_true')
    p.add_argument('--value-add-mse',action='store_true')
    p.add_argument('--direction-model-audit',action='store_true');p.add_argument('--directional-supervision',action='store_true')
    p.add_argument('--objective-audit',action='store_true')
    p.add_argument('--advantage-clip',type=float)
    p.add_argument('--phase-stability',action='store_true');p.add_argument('--freeze-phase-predictor',action='store_true')
    a=p.parse_args();run(a.root,a.checkpoint,a.output,a.horizon,a.seconds,a.actor_lr,a.fast,a.warm_model,a.freeze_critic,a.gradient_audit,a.real_critic,a.native_ppo,a.stochastic_actor,a.noisy_eval,a.decoupled,a.reward_audit,a.exact_reward,a.critic_weight,a.actor_batch,a.fresh_ticks,a.eval_interval,a.training_seed,a.analytic_failure,a.freeze_world,a.stop_phase_gradient,a.model_audit,a.integrated_model,a.regularized_model,a.value_model_audit,a.value_weighted_model,a.value_add_mse,a.direction_model_audit,a.directional_supervision,a.objective_audit,a.advantage_clip,a.phase_stability,a.freeze_phase_predictor,a.imagined_exact,a.heading_model,a.hard_imagined_failure,a.increment_model,a.audit_context,a.critic_context,a.gradient_fidelity,a.fit_dose,a.head_fit_mode,a.capacity_width,a.direct_tracking_gradient,a.offpolicy_td3,a.offpolicy_bc_alpha,a.native_awr,a.awr_replay_rollouts)
