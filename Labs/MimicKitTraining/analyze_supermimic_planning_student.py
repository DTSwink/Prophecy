import argparse
import json
from pathlib import Path
from analyze_supermimic_pilots import paired,GROUPS


def analyze(folder,names=('ppo','student')):
    folder=Path(folder);runs={a:json.loads((folder/a/'result.json').read_text()) for a in names}
    assert len({r['checkpoint_sha256'] for r in runs.values()})==1
    assert len({r['gpu'] for r in runs.values()})==1
    result=dict(kind='verified_planning_student_race',arms={},comparisons={},limitation='One training seed. Evaluation intervals are motion-cluster variation, not independent learning replications. All native planning and collection charged; normal episodes checked for300ticks.')
    for arm,r in runs.items():
        assert r['complete'] and r['accepted_actor_updates']>0
        if 'student_parameter_delta_l2' in r:
            assert r['original_parameter_max_abs_delta']==0 and r['student_parameter_delta_l2']>0
            assert all(b['reset_max_abs_error']<2e-4 and b['candidates']==16 for b in r['teacher_batches'])
        else:assert r['actor_parameter_delta_l2']>0
        if 'noise_audit' in r:
            assert r['noise_audit']['calls']==32*r['accepted_actor_updates']
            assert .95<r['noise_audit']['rms']<1.05
        item={k:r[k] for k in ['accepted_actor_updates','learning_seconds_excluding_checks','training_seconds','intermediate_evaluation_seconds','setup_and_baseline_seconds','final_evaluation_seconds','total_worker_seconds','actor_parameter_delta_l2','critic_parameter_delta_l2','stop_reason']}
        for k in ['student_parameter_delta_l2','teacher_batches','selected_student_update','validation_loss','student_max_updates','fit_audits','selected_fit_audit','teacher_data_sha256','teacher_data_bytes','final_fit_audit_and_data_save_seconds']:
            if k in r:item[k]=r[k]
        if 'noise_audit' in r:item['noise_audit']=r['noise_audit']
        item['improvements']={mode:{g:paired(r['initial'][mode],r['final'][mode],g) for g in GROUPS} for mode in ['deterministic','noisy']}
        result['arms'][arm]=item
    for mode in ['deterministic','noisy']:
        result['comparisons'][mode]={g:paired(runs[names[0]]['final'][mode],runs[names[1]]['final'][mode],g) for g in GROUPS}
    n=result['comparisons']['noisy']['perturbed_loco'];d=result['comparisons']['deterministic']['perturbed_loco']
    result['candidate_for_longer_independent_confirmation']=bool(n['failure_change_percentage_points']<=-1 and n['return_change_motion_cluster_interval_95'][0]>0 and d['failure_change_percentage_points']<=1 and all(result['comparisons'][m]['normal_loco']['failure_change_percentage_points']<=1 for m in ['deterministic','noisy']) and runs[names[1]]['learning_seconds_excluding_checks']<=runs[names[0]]['learning_seconds_excluding_checks']+5 and not runs[names[1]]['stop_reason'])
    if 'selected_fit_audit' in runs[names[1]]:
        candidate=runs[names[1]];audit=candidate['selected_fit_audit']
        result['fit_diagnostic']=dict(
            heldout_teacher_energy_explained=audit['teacher_valid']['explained_target_energy'],
            training_teacher_energy_explained=audit['teacher_train']['explained_target_energy'],
            heldout_anchor_rms=audit['anchor_valid']['prediction_rms'],
            teacher_collection_seconds=sum(b['seconds'] for b in candidate['teacher_batches']),
            noncollection_learning_seconds=candidate['learning_seconds_excluding_checks']-sum(b['seconds'] for b in candidate['teacher_batches']),
            caveat='Lower imitation error is not physical policy improvement; see actual simulator comparison. Saved dataset enables exact later checks without recollection.')
        result['candidate_for_longer_independent_confirmation'] &= bool(
            candidate['learning_seconds_excluding_checks']+candidate['final_fit_audit_and_data_save_seconds']<=runs[names[0]]['learning_seconds_excluding_checks']+5
            and result['arms'][names[1]]['improvements']['noisy']['perturbed_loco']['failure_change_percentage_points']<0)
    if names==['white','colored'] or names==('white','colored'):
        result['kind']='verified_colored_noise_ppo_race'
        assert runs['white']['noise_audit']['beta']==0 and runs['colored']['noise_audit']['beta']==.5
        assert abs(runs['white']['noise_audit']['lag1_product'])<.02 and runs['colored']['noise_audit']['lag1_product']>.2
    (folder/'verified-student.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder');p.add_argument('--arms',nargs=2,default=['ppo','student']);args=p.parse_args();analyze(args.folder,args.arms)
