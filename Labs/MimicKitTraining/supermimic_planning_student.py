"""Isolated native-PPO versus simulator-planned residual imitation.

The student receives only the existing normalized observation. No episode age,
perturbation flag, future state, planner or critic is available at deployment.
Planning and teacher collection count against the same training-time budget.
"""
import argparse
import hashlib
import os
from pathlib import Path
import sys
import time
import types
from contextlib import contextmanager

import torch
from torch import nn
import supermimic_race as base
from supermimic_planning_probe import elite_distribution, accumulate, residual_scale


class ResidualStudent(nn.Module):
    def __init__(self, inputs=154):
        super().__init__()
        self.net=nn.Sequential(nn.Linear(inputs,256),nn.SiLU(),nn.Linear(256,256),nn.SiLU(),nn.Linear(256,34))
        nn.init.zeros_(self.net[-1].weight);nn.init.zeros_(self.net[-1].bias)

    def forward(self, obs):
        return .225*torch.tanh(self.net(obs))


def install(model, student):
    """Preserve original policy, phase and exploration; change motor mean only."""
    original=model.eval_actor
    model.add_module('_planning_student',student)
    model._planning_student_enabled=False
    def evaluate(this,obs):
        dist=original(obs)
        if this._planning_student_enabled:
            dist=type(dist)(mean=dist.mode+student(obs),logstd=dist.logstd)
        return dist
    model.eval_actor=types.MethodType(evaluate,model)


def sample_part(data, key, count, generator):
    x,y=data[key]
    ids=torch.randint(len(x),(count,),device=x.device,generator=generator)
    return x[ids],y[ids]


@torch.no_grad()
def audit_student_fit(student, data, chunk_size=4096):
    """Full split errors against an explicit zero-residual baseline."""
    result={}
    for key,(x,y) in data.items():
        assert len(x)==len(y) and len(x)>0
        error=0.;zero=0.;prediction=0.;count=0
        for xx,yy in zip(x.split(chunk_size),y.split(chunk_size)):
            pred=student(xx)
            error+=float((pred-yy).square().sum())
            zero+=float(yy.square().sum());prediction+=float(pred.square().sum())
            count+=yy.numel()
        result[key]=dict(samples=len(x),mse=error/count,zero_residual_mse=zero/count,
                         explained_target_energy=None if zero==0 else 1-error/zero,
                         prediction_rms=(prediction/count)**.5)
    return result


@contextmanager
def preserve_random_state():
    cpu=torch.get_rng_state();cuda=torch.cuda.get_rng_state_all() if torch.cuda.is_initialized() else None
    numpy=base.np.random.get_state();python=base.random.getstate()
    try:yield
    finally:
        torch.set_rng_state(cpu)
        if cuda is not None:torch.cuda.set_rng_state_all(cuda)
        base.np.random.set_state(numpy);base.random.setstate(python)


def run(root, checkpoint, output, arm, seconds=300, training_seed=849120, noise_beta=None, evaluation_seed=984120, check_interval=None,
        student_max_updates=1000, audit_student=False):
    started=time.perf_counter();root=Path(root).resolve();output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    sys.path[:0]=[str(root/'pipeline'),str(root/'MimicKit/mimickit')];os.chdir(root/'MimicKit')
    os.environ['PYGLET_HEADLESS']='true';torch.set_num_threads(2)
    import warp as wp,yaml,mujoco_warp as mjw
    from util import mp_util
    from perturbed_omni import PerturbedOmniEnv
    from omni_policy import OmniPPOAgent
    from resume import restore,migrate_physical_observation_scales,override_actor_learning_rate
    from learning.base_agent import AgentMode
    from envs.base_env import DoneFlags
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6842)
    base.seed(training_seed)
    cfg,ec,ac=[yaml.safe_load((root/'prepared'/(n+'_config.yaml')).read_text()) for n in ['env','engine','agent']]
    env=PerturbedOmniEnv(cfg,ec,1024,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0')
    restored=restore(agent,checkpoint);override_actor_learning_rate(agent,1.125e-6)
    if cfg.get('perturbed_motion',{}).get('observation_normalization')=='physical_scales_v1':migrate_physical_observation_scales(agent)
    agent._init_train();assert not agent._need_normalizer_update()
    original={k:v.detach().clone() for k,v in agent.state_dict().items()}
    original_actor=[p.detach().clone() for p in agent._model.get_actor_params()]
    original_critic=[p.detach().clone() for p in agent._model.get_critic_params()]
    assert student_max_updates>0
    assert arm=='student' or (student_max_updates==1000 and not audit_student)
    student=None
    sampler=None
    if noise_beta is not None:
        assert arm=='ppo'
        from supermimic_colored_noise import install as install_noise
        sampler=install_noise(agent._model,noise_beta,training_seed+300000,length=1024)
    if arm=='student':
        for p in agent.parameters():p.requires_grad_(False)
        student=ResidualStudent().to('cuda:0');install(agent._model,student)
        initial_student=[p.detach().clone() for p in student.parameters()]
        optimizer=torch.optim.Adam(student.parameters(),lr=3e-4)
    report=dict(kind='native_planning_student_race',arm=arm,complete=False,restored=restored,
                training_seed=training_seed,checkpoint_sha256=hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest(),
                gpu=torch.cuda.get_device_name(),seconds_budget=seconds,updates=[],teacher_batches=[],evaluations=[],
                stop_reason=None,accepted_actor_updates=0,prior_fitting_seconds=0,
                student_inputs='Existing154 normalized observation only; no age/perturbation/critic/planner at inference.',
                training_recipe='Zero-initial2x256SiLU residual, bound.225; original motors/phase/critic frozen. Adam3e-4, equal early-teacher/zero-anchor MSE. Four fresh reset batches,16CEM candidates each,32tick rank,8tick residual. Fit at most1000updates. Hold out whole worlds mod10 for BC validation. All planning/collection/fit charged.')
    if check_interval is not None:
        assert arm=='ppo' and noise_beta is not None and check_interval>0
        report['repeated_check_interval_seconds']=check_interval
        report['evaluation_preserves_training_rng']=True
    if arm=='student':
        report['student_max_updates']=student_max_updates
        report['training_recipe']=report['training_recipe'].replace('at most1000updates',f'at most{student_max_updates}updates')
        if audit_student:report['fit_audits']=[]
    def emit(marker,**values):
        import json
        print(marker,json.dumps(values),flush=True)
    if arm=='ppo':report['training_recipe']='Restored native PPO, Adam actor1.125e-6; original task, clipping, phase and critic updates.'
    if sampler is not None:
        report.update(kind='colored_ppo_race',noise_beta=noise_beta,noise_sequence_length=1024)
        report['training_recipe']+=' CN-PPO sampling only, Gaussian marginals, unit theoretical variance; no reset at episode boundaries as in primary implementation. Existing independent-noise evaluation unchanged.'
    emit('STUDENT_ENV_READY',arm=arm,noise_beta=noise_beta,seconds=time.perf_counter()-started)
    def evaluation(seeds,ticks):
        if student is not None:agent._model._planning_student_enabled=True
        result={}
        for label,noisy in [('deterministic',False),('noisy',True)]:
            result[label]=dict(rows=base.evaluate(env,agent,seeds,max_ticks=ticks,exploration=noisy))
            emit('STUDENT_EVAL_PROGRESS',arm=arm,mode=label,ticks=ticks,seeds=seeds)
        return result
    report['initial']=evaluation([evaluation_seed,evaluation_seed+1],300)
    if sampler is not None:assert sampler.calls==0,'Evaluation consumed colored training noise'
    def rate(ev, group=2):
        rows=ev['rows'];selected=[(g==group,f) for r in rows for g,f in zip(r['row_group'],r['row_failed'])]
        return 100*sum(f for s,f in selected if s)/sum(s for s,_ in selected)
    emit('STUDENT_BASELINE',arm=arm,det=rate(report['initial']['deterministic']),noisy=rate(report['initial']['noisy']))
    report['setup_and_baseline_seconds']=time.perf_counter()-started;base.write(output/'result.json',report)
    clock=time.perf_counter();eval_seconds=0.;next_progress=0.;next_check=float(check_interval or 150)
    def elapsed():return time.perf_counter()-clock-eval_seconds
    def reset_train():
        agent.train();agent.set_mode(AgentMode.TRAIN)
        mjw.reset_data(env._engine._solver.mjw_model,env._engine._solver.mjw_data)
        agent._curr_obs,agent._curr_info=agent._reset_envs()
    base.seed(training_seed);reset_train()
    zero=torch.zeros(1024,34,device='cuda:0');worlds=torch.arange(1024,device='cuda:0')
    data={key:[] for key in ['teacher_train','teacher_valid','anchor_train','anchor_valid']}
    packed=None;generator=torch.Generator(device='cuda:0').manual_seed(training_seed+100000)
    best_validation=float('inf');best_weights=None;best_update=None;dataset_generation=0

    @torch.no_grad()
    def plan_batch(reset_seed):
        agent.eval();agent.set_mode(AgentMode.TEST);agent._model._planning_student_enabled=False
        batch_started=time.perf_counter();initial_obs=None;initial_motion=None;reset_error=0.;part={k:[] for k in data}
        def rollout(bias,horizon,collect=False):
            nonlocal initial_obs,initial_motion,reset_error
            base.seed(reset_seed);mjw.reset_data(env._engine._solver.mjw_model,env._engine._solver.mjw_data)
            obs,info=agent._reset_envs();motion=env._motion_ids.clone();scope=env._perturbed_rows&(env._gaits[motion]!=-1)
            if initial_obs is None:initial_obs=obs.clone();initial_motion=motion.clone()
            error=float((obs-initial_obs).abs().max());reset_error=max(error,reset_error)
            assert error<2e-4 and torch.equal(initial_motion,motion)
            bias=bias*scope[:,None];active=torch.ones(1024,device='cuda:0',dtype=torch.bool)
            failed=torch.zeros_like(active);total=torch.zeros(1024,device='cuda:0');disc=torch.zeros_like(total);boot=torch.zeros_like(total)
            for tick in range(horizon):
                agent._decide_action(obs,info)
                norm=agent._obs_norm.normalize(obs);raw=agent._model.eval_actor(norm).mode
                delta=residual_scale(tick)*bias
                if collect:
                    early=active&scope&(tick<8)
                    anchor=active&(~early)&((tick<8) or tick%8==0)
                    for name,mask in [('teacher',early),('anchor',anchor)]:
                        for split,held in [('train',False),('valid',True)]:
                            selected=mask&((worlds%10==0)==held)
                            if bool(selected.any()):part[name+'_'+split].append((norm[selected].clone(),delta[selected].clone()))
                nxt,reward,done,info=env.step(agent._a_norm.unnormalize(raw+delta))
                ended=done!=DoneFlags.NULL.value;fail=done==DoneFlags.FAIL.value
                assert torch.isfinite(reward).all()
                value=agent._model.eval_critic(agent._obs_norm.normalize(nxt)).squeeze(-1)
                boot+=.99**(tick+1)*active*ended*(~fail)*value
                active,failed,total,disc=accumulate(active,failed,total,disc,reward,ended,fail,tick)
                obs,info=agent._reset_done_envs(done)
            return disc+boot+.99**horizon*active*value
        mean=zero.clone();sigma=torch.full_like(mean,.075);best=zero.clone()
        rng=torch.Generator(device='cuda:0').manual_seed(reset_seed+3000000)
        for round_id in range(2):
            sampled=(mean[None]+sigma[None]*torch.randn((6,1024,34),device='cuda:0',generator=rng)).clamp(-.225,.225)
            candidates=torch.cat([zero[None],best[None],sampled])
            scores=torch.stack([rollout(bias,32) for bias in candidates])
            best=candidates[scores.argmax(0),worlds].clone();mean,sigma=elite_distribution(candidates,scores)
            emit('STUDENT_PLANNING',reset_seed=reset_seed,round=round_id,training_seconds=elapsed())
        rollout(best,120,True)
        for key in data:data[key].extend(part[key])
        item=dict(reset_seed=reset_seed,seconds=time.perf_counter()-batch_started,reset_max_abs_error=reset_error,
                  samples={k:sum(len(x) for x,y in v) for k,v in part.items()},candidates=16,planning_horizon=32,
                  residual_rms=float(best.square().mean().sqrt()))
        report['teacher_batches'].append(item);emit('STUDENT_TEACHER_DATA',**item)

    while elapsed()<seconds:
        if (output/'STOP_REQUEST').exists():
            report['stop_reason']='Paired candidate regressed; stop requested by isolated comparison controller'
            break
        if arm=='ppo':
            agent._iter=report['accepted_actor_updates']
            metrics={k:float(v) for k,v in agent._train_iter().items()}
            agent._sample_count=agent._update_sample_count();report['accepted_actor_updates']+=1
        else:
            # One fresh teacher batch per150 fits; stop adding batches after four.
            updates=report['accepted_actor_updates']
            if len(report['teacher_batches'])<4 and updates>=150*len(report['teacher_batches']):
                # Do not launch a new ~55s planning batch near the time limit.
                if len(report['teacher_batches']) and elapsed()>seconds-65:break
                plan_batch(training_seed+1000+len(report['teacher_batches']))
                packed={k:(torch.cat([x for x,y in rows]),torch.cat([y for x,y in rows])) for k,rows in data.items()}
                assert all(len(x)>0 for x,y in packed.values())
                dataset_generation+=1;best_validation=float('inf');best_weights=None
            if elapsed()>=seconds or updates>=student_max_updates:break
            student.train()
            tx,ty=sample_part(packed,'teacher_train',512,generator);ax,ay=sample_part(packed,'anchor_train',512,generator)
            teacher_loss=(student(tx)-ty).square().mean();anchor_loss=(student(ax)-ay).square().mean()
            loss=(teacher_loss+anchor_loss)/.075**2
            optimizer.zero_grad(set_to_none=True);loss.backward();norm=nn.utils.clip_grad_norm_(student.parameters(),1.)
            assert torch.isfinite(norm);optimizer.step();report['accepted_actor_updates']+=1
            metrics=dict(teacher_mse=float(teacher_loss),anchor_mse=float(anchor_loss),dataset_generation=dataset_generation)
            if report['accepted_actor_updates']%25==0:
                with torch.no_grad():
                    errors={}
                    for key in ['teacher_valid','anchor_valid']:
                        x,y=packed[key];errors[key]=float((student(x)-y).square().mean())
                    valid=sum(errors.values())
                    if valid<best_validation:
                        best_validation=valid;best_weights={k:v.detach().clone() for k,v in student.state_dict().items()};best_update=report['accepted_actor_updates']
                    metrics.update(errors)
            if audit_student and report['accepted_actor_updates'] in (1000,5000,10000,20000):
                audit=dict(updates=report['accepted_actor_updates'],dataset_generation=dataset_generation,
                           training_seconds=elapsed(),splits=audit_student_fit(student,packed))
                report['fit_audits'].append(audit);emit('STUDENT_FIT_AUDIT',**audit)
        row=dict(seconds=elapsed(),accepted_actor_updates=report['accepted_actor_updates'],metrics=metrics)
        if elapsed()>=next_progress:
            report['updates'].append(row);base.write(output/'result.json',report);emit('STUDENT_PROGRESS',arm=arm,**row);next_progress=elapsed()+15
        if elapsed()>=next_check and elapsed()<seconds:
            training_at_check=elapsed();check_started=time.perf_counter()
            if check_interval is None:ev=evaluation([evaluation_seed],120)
            else:
                calls=sampler.calls
                with preserve_random_state():ev=evaluation([evaluation_seed,evaluation_seed+1],120)
                assert sampler.calls==calls,'Evaluation consumed training exploration'
            report['evaluations'].append(dict(training_seconds=training_at_check,**ev))
            bad=rate(ev['noisy'])>rate(report['initial']['noisy'])+5 or rate(ev['deterministic'],0)>3
            emit('STUDENT_CHECK',arm=arm,noisy=rate(ev['noisy']),det=rate(ev['deterministic']),bad=bad)
            eval_seconds+=time.perf_counter()-check_started;next_check=next_check+check_interval if check_interval else float('inf')
            if bad:
                report['stop_reason']='Early native-simulator regression';base.write(output/'result.json',report);break
            if arm=='ppo':reset_train()
    report['learning_seconds_excluding_checks']=elapsed();report['intermediate_evaluation_seconds']=eval_seconds
    report['training_seconds']=time.perf_counter()-clock
    if student is not None:
        if best_weights is not None:student.load_state_dict(best_weights)
        if audit_student:
            audit_started=time.perf_counter()
            report['selected_fit_audit']=audit_student_fit(student,packed)
            data_path=output/'teacher_data.pt'
            torch.save(dict(data={k:tuple(t.detach().cpu() for t in pair) for k,pair in packed.items()},
                            checkpoint_sha256=report['checkpoint_sha256'],training_seed=training_seed,
                            teacher_batches=report['teacher_batches'],
                            split='Whole worlds modulo10; no evaluation reset seeds used'),data_path)
            report['teacher_data_sha256']=hashlib.sha256(data_path.read_bytes()).hexdigest()
            report['teacher_data_bytes']=data_path.stat().st_size
            report['final_fit_audit_and_data_save_seconds']=time.perf_counter()-audit_started
            emit('STUDENT_FIT_SELECTED',updates=best_update,splits=report['selected_fit_audit'],
                 data_sha256=report['teacher_data_sha256'])
        report['selected_student_update']=best_update;report['validation_loss']=best_validation
        report['student_parameter_delta_l2']=float(sum((p-q).square().sum() for p,q in zip(student.parameters(),initial_student)).sqrt())
        report['original_parameter_max_abs_delta']=max(float((v-original[k]).abs().max()) for k,v in agent.state_dict().items() if k in original)
        assert report['original_parameter_max_abs_delta']==0 and report['student_parameter_delta_l2']>0
        torch.save(student.state_dict(),output/'student_final.pt')
    report['actor_parameter_delta_l2']=float(sum((p-q).square().sum() for p,q in zip(agent._model.get_actor_params(),original_actor)).sqrt())
    report['critic_parameter_delta_l2']=float(sum((p-q).square().sum() for p,q in zip(agent._model.get_critic_params(),original_critic)).sqrt())
    if sampler is not None:
        report['noise_audit']=sampler.audit()
        assert sampler.calls==32*report['accepted_actor_updates']
    final_started=time.perf_counter();report['final']=evaluation([evaluation_seed,evaluation_seed+1],300)
    report['final_evaluation_seconds']=time.perf_counter()-final_started
    report['complete']=True;report['total_worker_seconds']=time.perf_counter()-started
    torch.save(agent.state_dict(),output/'policy_final.pt');base.write(output/'result.json',report)
    emit('STUDENT_COMPLETE',arm=arm,updates=report['accepted_actor_updates'],learning_seconds=report['learning_seconds_excluding_checks'],
         noisy=rate(report['final']['noisy']),det=rate(report['final']['deterministic']),total_seconds=report['total_worker_seconds'])


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ['root','checkpoint','output','arm']:p.add_argument('--'+k,required=True)
    p.add_argument('--seconds',type=float,default=300);p.add_argument('--training-seed',type=int,default=849120)
    p.add_argument('--noise-beta',type=float);p.add_argument('--evaluation-seed',type=int,default=984120)
    p.add_argument('--check-interval',type=float)
    p.add_argument('--student-max-updates',type=int,default=1000)
    p.add_argument('--audit-student',action='store_true')
    run(**vars(p.parse_args()))
