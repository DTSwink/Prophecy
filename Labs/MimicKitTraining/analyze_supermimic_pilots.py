"""Validate isolated pilot reports and paired actual-simulator outcomes."""
import argparse,json
from pathlib import Path
import numpy as np

GROUPS=['normal_loco','normal_idle','perturbed_loco','perturbed_idle']


def paired(first,last,group):
    def rows(e):
        result={}
        for r in e['rows']:
            for i,g in enumerate(r['row_group']):
                if GROUPS[g]==group:
                    result[(r['seed'],i)]=(r['row_motion'][i],r['row_failed'][i],r['row_return'][i],r['row_ticks'][i])
        return result
    a,b=rows(first),rows(last)
    assert a.keys()==b.keys(),'Evaluation episode sets differ'
    keys=sorted(a);assert all(a[k][0]==b[k][0] for k in keys),'Motion assignments differ'
    before=np.array([a[k][1:] for k in keys],float);after=np.array([b[k][1:] for k in keys],float)
    delta=after-before;motion=np.array([a[k][0] for k in keys]);clusters=np.unique(motion)
    rng=np.random.default_rng(820417);means=[]
    for _ in range(1000):
        chosen=rng.choice(clusters,len(clusters),replace=True)
        means.append(np.concatenate([delta[motion==m] for m in chosen]).mean(0))
    interval=np.quantile(means,[.025,.975],axis=0)
    return dict(episodes=len(keys),before_failures=int(before[:,0].sum()),after_failures=int(after[:,0].sum()),
        before_failure_percent=float(before[:,0].mean()*100),after_failure_percent=float(after[:,0].mean()*100),
        failure_change_percentage_points=float(delta[:,0].mean()*100),
        failure_change_motion_cluster_interval_95=(interval[:,0]*100).tolist(),
        before_return=float(before[:,1].mean()),after_return=float(after[:,1].mean()),
        return_change_motion_cluster_interval_95=interval[:,1].tolist(),
        before_ticks=float(before[:,2].mean()),after_ticks=float(after[:,2].mean()))


def analyze(folder,arms):
    folder=Path(folder);summary=dict(arms={},comparisons={},limitation='One training seed per arm; intervals reflect evaluation motion/reset variation only, not reproducibility across training seeds.')
    reports={name:json.loads((folder/name/'result.json').read_text()) for name in arms}
    assert len({r['checkpoint_sha256'] for r in reports.values()})==1
    assert len({r['gpu'] for r in reports.values()})==1
    for name,r in reports.items():
        assert r['complete'] and r['accepted_actor_updates']>0 and r['actor_parameter_delta_l2']>0,'Actor did not actually update'
        assert r['quick_check_ticks']==r['final_evaluation_ticks'],'Initial/final evaluation horizons differ'
        item={k:r[k] for k in ['accepted_actor_updates','actor_parameter_delta_l2','training_seconds','intermediate_evaluation_seconds','learning_seconds_excluding_checks','stop_reason']}
        for k in ['training_seed','setup_and_baseline_seconds','final_evaluation_seconds','total_worker_seconds']:
            if k in r:item[k]=r[k]
        if r.get('actor_activation'):
            from supermimic_smooth_actor import acceptable
            activation=r['actor_activation']
            assert activation['mode'] in ('relu','smooth')
            assert activation['parameter_max_abs_delta']==0
            assert acceptable(activation['trials'][-1]) and acceptable(activation['heldout'],2.)
            assert activation['beta']==activation['trials'][-1]['beta']
            assert r['training_seed']==849108 and r['horizon']==8
            assert all([row['seed'] for row in ev['rows']]==[984107,984108] for ev in r['evaluations'])
            item['actor_activation']=activation
        if 'phase_stability' in r:
            probe=r['final_phase_stability']
            assert all(np.isfinite(v) for v in probe.values()),'Nonfinite phase drift measurement'
            assert probe['predictor_parameter_delta_l2']==0.,'Fixed predictor weights changed'
            if r['phase_stability']['freeze_perturbed']:
                assert probe['deployed_fixed_probe_drift_rms_cycles']==0.,'Fixed feedback predictor drifted'
            item['phase_stability']=r['phase_stability']
            item['final_phase_stability']=probe
        if r.get('freeze_world',False):
            assert r['world_model_parameter_delta_l2']==0.,'Frozen audited model changed during policy test'
            item['world_model_parameter_delta_l2']=0.
        if name in ('ppo_world','ppo_short'):
            actor_rows=[u['metrics'] for u in r['updates'] if 'actor_step_delta_l2' in u['metrics']]
            assert actor_rows and all(u['forward_mode']=='native_ppo_learned_rollout' and not u['world_derivatives_used'] for u in actor_rows)
            assert all(u['imagined_transitions']==32768 and u['policy_kl']<=.180001 for u in actor_rows)
            assert sum(u['actor_steps_accepted'] for u in actor_rows)>0
            item['detached_native_ppo_world_verified']=True
            item['imagined_rollout_seconds_mean']=float(np.mean([u['imagined_rollout_seconds'] for u in actor_rows]))
            item['ppo_update_seconds_mean']=float(np.mean([u['ppo_update_seconds'] for u in actor_rows]))
            if name=='ppo_short':
                assert all(u['branch_horizon']==8 and u['imagined_branch_cuts']>0 for u in actor_rows)
                item['short_branch_horizon_verified']=8
                if all('model_validation_horizon' in u for u in actor_rows):
                    assert all(u['model_validation_horizon']==8 for u in actor_rows) and r['horizon']==8
                    item['matched_model_validation_horizon_verified']=8
        if r.get('fully_imagined_exact_reward',False) and r.get('critic_weight',1.)==0.:
            assert r['critic_parameter_delta_l2']==0., 'Critic-free candidate changed critic parameters'
            actor_rows=[u['metrics'] for u in r['updates'] if 'actor_loss' in u['metrics']]
            assert actor_rows and all(not u['critic_enabled'] and u['critic_loss']==0. and u['imagined_terminal_value']==0. for u in actor_rows)
            item['critic_free_verified']=True
        if r.get('fully_imagined_exact_reward',False) and r.get('stochastic_imagination',False):
            actor_rows=[u['metrics'] for u in r['updates'] if 'actor_loss' in u['metrics']]
            assert actor_rows and all(u['stochastic_imagination'] and u['imagined_action_noise_rms']>0. for u in actor_rows)
            item['stochastic_full_imagination_verified']=True
            item['imagined_action_noise_rms_range']=[min(u['imagined_action_noise_rms'] for u in actor_rows),max(u['imagined_action_noise_rms'] for u in actor_rows)]
        if r.get('fully_imagined_exact_reward',False) and r.get('stop_phase_gradient',False):
            actor_rows=[u['metrics'] for u in r['updates'] if 'actor_loss' in u['metrics']]
            assert actor_rows and all(u['stop_phase_gradient'] for u in actor_rows)
            assert all(u['phase_head_gradient_norm'] is not None and np.isfinite(u['phase_head_gradient_norm']) for u in actor_rows)
            item['full_phase_detachment_verified']=True
            item['phase_head_gradient_norm_range']=[min(u['phase_head_gradient_norm'] for u in actor_rows),max(u['phase_head_gradient_norm'] for u in actor_rows)]
        if r.get('critic_task_context'):
            installation=r['critic_task_context']
            assert installation['initial_value_max_error']==0. and installation['initial_actor_max_error']==0.
            assert r['critic_context_weight_l2']>0., 'Context projection never learned'
            actor_rows=[u['metrics'] for u in r['updates'] if 'actor_loss' in u['metrics']]
            assert actor_rows and all(u['critic_task_context'] and u['critic_context_weight_l2']>0. for u in actor_rows)
            item['critic_task_context_verified']=installation
            item['critic_context_weight_l2']=r['critic_context_weight_l2']
        if r.get('direct_tracking_gradient',False):
            actor_rows=[u['metrics'] for u in r['updates'] if 'actor_loss' in u['metrics']]
            scales=[u['direct_tracking_scale'] for u in actor_rows]
            assert actor_rows and all(u['direct_tracking_gradient'] for u in actor_rows)
            assert all(np.isfinite(v) and 0<v<=1 for v in scales)
            assert len(set(scales))==1, 'Tracking gradient calibration changed during training'
            item['direct_tracking_gradient_verified']=True
            item['fixed_tracking_gradient_scale']=scales[0]
        if r.get('offpolicy_td3'):
            assert r['q_warmup']['gate'] and r['q_warmup']['actor_delta_l2']==0
            assert r['initial_phase_max_error']<2e-4 and r['initial_phase_same_batch_max_error']<1e-6
            assert r['initial_action_max_error']==0
            item['q_warmup']=r['q_warmup']
            item['recipe']=r['recipe']
            item['critic_updates']=r['critic_updates']
            if r['recipe'].get('bc_alpha',0):
                assert r['recipe']['preserved_initial_data_fraction']==.5
                actor_rows=[u['metrics'] for u in r['updates'] if 'actor_loss' in u['metrics']]
                assert actor_rows and all(np.isfinite(u['q_weight']) and u['q_weight']>0 and u['behavior_cloning_loss']>=0 for u in actor_rows)
                item['behavior_regularization_verified']=True
        if r.get('native_awr'):
            source=r['native_awr']
            assert source['source_sha256']=='71a7233a87a0df690fbcadafd4781f0de83dd3be07bd1c84913458c4b1f4f3e9'
            rows=[u['metrics'] for u in r['updates']]
            assert rows and all(u['awr_audit_critic_target_max_error']==0. for u in rows)
            assert all(0<u['awr_audit_weight_effective_sample_fraction']<=1.000001 for u in rows)
            assert all(0<u['awr_audit_weight_max']<=source['weight_clip'] for u in rows)
            assert sum(u.get('actor_steps_accepted',0) for u in rows)>0
            if source.get('replay_rollouts',1)>1:
                assert source['refresh_weights_after_critic']
                assert max(u['awr_audit_replay_rollouts'] for u in rows)==source['replay_rollouts']
                assert all(u['awr_audit_refreshed_after_critic']==1. for u in rows)
                assert len({u['awr_audit_actor_steps_requested'] for u in rows})==1
                assert len({u['awr_audit_critic_steps_requested'] for u in rows})==1
            item['native_awr_verified']=source
        if r.get('model_pretraining_accounting'):
            prior=r['model_pretraining_accounting'];item['model_pretraining_accounting']=prior
            names=['fit_seconds','collection_seconds','worker_setup_seconds','parent_setup_seconds']
            item['known_prior_preparation_seconds']=sum(prior['prior_'+k] if 'prior_'+k in prior else prior[k] for k in names)
            item['known_prior_preparation_seconds']+=prior.get('normalization_seconds',0.)
            summary['timing_warning']='Post-fit policy comparison. Reused model fitting, data collection and setup are additional costs, not a free learning speedup.'
        for source,mode in [('evaluations','deterministic'),('noisy_evaluations','noisy')]:
            if source not in r:continue
            first,last=r[source][0],r[source][-1]
            errors=[row.get('initial_max_abs_error') for e in r[source] for row in e['rows']]
            item[mode]=dict(groups={g:paired(first,last,g) for g in GROUPS},
                reset_max_abs_error=max(errors) if all(x is not None for x in errors) else None,
                initial_final_hashes_match=[x['initial_observation_sha256']==y['initial_observation_sha256'] for x,y in zip(first['rows'],last['rows'])])
            if item[mode]['reset_max_abs_error'] is not None:assert item[mode]['reset_max_abs_error']<=2e-4
        summary['arms'][name]=item
    if len(arms)==2:
        a,b=arms
        elapsed=[reports[n]['learning_seconds_excluding_checks'] for n in [a,b]]
        gap=abs(elapsed[0]-elapsed[1])
        summary['comparison_timing']=dict(arms=[a,b],actual_learning_seconds=elapsed,
            absolute_gap_seconds=gap,approximately_matched=gap<=max(5.,.05*min(elapsed)),
            note='Final outcome comparison is not a matched-time speed claim if durations differ materially; reused setup/fitting costs remain additional.')
        for source,mode in [('evaluations','deterministic'),('noisy_evaluations','noisy')]:
            if source not in reports[a] or source not in reports[b]:continue
            summary['comparisons'][mode]=dict(first_arm=a,second_arm=b,
                groups={g:paired(reports[a][source][-1],reports[b][source][-1],g) for g in GROUPS})
    if arms==['relu','smooth']:
        assert all(r.get('actor_activation') for r in reports.values())
        assert reports['relu']['actor_activation']['beta']==reports['smooth']['actor_activation']['beta']
        noisy=summary['comparisons']['noisy']['groups']
        deterministic=summary['comparisons']['deterministic']['groups']
        summary['candidate_for_independent_ppo_confirmation']=bool(
            summary['comparison_timing']['approximately_matched']
            and all(r['stop_reason'] is None for r in reports.values())
            and noisy['perturbed_loco']['failure_change_percentage_points']<=-2.
            and noisy['perturbed_loco']['return_change_motion_cluster_interval_95'][0]>0
            and deterministic['perturbed_loco']['failure_change_percentage_points']<=1.
            and all(x['normal_loco']['failure_change_percentage_points']<=1. for x in [noisy,deterministic]))
        summary['timing_warning']='This isolates activation in the model learner, not a native-PPO speed comparison. Prior326.30s model fit plus setup and conversion checks are extra. Full normal300tick evaluation and independent training seeds remain required.'
    if arms==['online','target']:
        for name,r in reports.items():
            assert r['target_critic_ablation']['method']==name and r['training_seed']==849140
            actor_rows=[u['metrics'] for u in r['updates'] if 'actor_loss' in u['metrics']]
            assert actor_rows and all(u['separate_bootstrap_critic']==(name=='target') for u in actor_rows)
            assert r['target_critic_ablation']['updates']==len(actor_rows)
            if name=='target':
                assert all(u['target_retention']==.4 for u in actor_rows)
                assert [u['target_update_count'] for u in actor_rows]==list(range(1,len(actor_rows)+1))
                assert actor_rows[-1]['target_delta_l2']>0 and actor_rows[-1]['target_online_gap_l2']>0
                summary['arms'][name]['target_critic_audit']={k:actor_rows[-1][k] for k in
                    ['target_retention','target_update_count','target_delta_l2','target_online_gap_l2']}
        noisy=summary['comparisons']['noisy']['groups'];det=summary['comparisons']['deterministic']['groups']
        summary['candidate_for_independent_ppo_confirmation']=bool(
            summary['comparison_timing']['approximately_matched']
            and all(r['stop_reason'] is None for r in reports.values())
            and noisy['perturbed_loco']['failure_change_percentage_points']<=-2.
            and noisy['perturbed_loco']['return_change_motion_cluster_interval_95'][0]>0
            and det['perturbed_loco']['failure_change_percentage_points']<=1.
            and all(x['normal_loco']['failure_change_percentage_points']<=1. for x in [noisy,det]))
        summary['timing_warning']='SHAC-style target bootstrap versus online-critic model learner, not a native-PPO speed comparison. Prior326.300588s model preparation additional. Full300tick normal evaluation and independent training seeds still required.'
    (folder/'verified-comparison.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder');p.add_argument('arms',nargs='+');a=p.parse_args()
    analyze(a.folder,a.arms)
