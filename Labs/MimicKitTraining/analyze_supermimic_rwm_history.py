"""Compare held-out prediction calibration, never call it policy improvement."""
import json
from pathlib import Path
import sys


def aggregate(result):
    groups={}
    for run in result['calibration']:
        for row in run['predictions']:
            mode='noisy' if run['noisy'] else 'deterministic'
            kind='closed_loop' if row['closed_loop'] else 'logged_control'
            for name,value in row['groups'].items():
                if not value['rows']:continue
                key=f'{mode}/{kind}/h{row["horizon"]}/{name}'
                g=groups.setdefault(key,dict(rows=0,real_failures=0,predicted_failures=0,false_negative=0,false_positive=0,return_mae_sum=0))
                for k in ['rows','real_failures','predicted_failures','false_negative','false_positive']:g[k]+=value[k]
                g['return_mae_sum']+=value['rows']*value['return_mae']
    for g in groups.values():
        g['return_mae']=g.pop('return_mae_sum')/g['rows']
        g['real_failure_percent']=100*g['real_failures']/g['rows']
        g['predicted_failure_percent']=100*g['predicted_failures']/g['rows']
        g['missed_failure_fraction']=g['false_negative']/max(1,g['real_failures'])
    return groups


def main(folder,com2=False,failure_replay=False):
    candidate='failure_replay' if failure_replay else 'com2' if com2 else 'recurrent'
    folder=Path(folder);arms={name:json.loads((folder/('com2_model' if name=='com2' else name)/'result.json').read_text()) for name in ['control',candidate]}
    for name,r in arms.items():
        assert r['complete'] and r['method']==name and r['actor_updates']==0 and r['policy_max_abs_delta']==0
        assert r['optimizer_steps']>0 and r['model_parameter_delta_l2']>0
        for run in r['calibration']:assert run['audit']['hard_event_mismatches']==0 and run['audit']['score_max_error']<.002
    left,right=arms['control'],arms[candidate]
    for key in ['checkpoint_sha256','warm_sha256','dataset_sha256']:assert left[key]==right[key]
    if candidate=='recurrent':assert right['initial_prediction_max_abs_delta']==0
    if com2:
        assert left['task_weight']==0 and right['task_weight']>0
        assert left['simulator_com2_max_abs_error_mps']<.002 and right['simulator_com2_max_abs_error_mps']<.002
        assert abs(left['task_loss_calibration']['coefficient']-right['task_loss_calibration']['coefficient'])<1e-4
    assert abs(left['checks'][0]['metrics']['h8']['state_nse']-right['checks'][0]['metrics']['h8']['state_nse'])<1e-5
    groups={n:aggregate(r) for n,r in arms.items()}
    result=dict(kind='verified_com2_prediction_comparison' if com2 else 'verified_rwm_prediction_comparison',arms={},differences={},
        limitation='One fit seed; frozen actors. Overlapping branch cohorts are correlated. This measures prediction quality, not policy learning or a speedup.')
    for n,r in arms.items():
        result['arms'][n]=dict(fit_seconds=r['fit_seconds'],optimizer_steps=r['optimizer_steps'],total_seconds=r['total_seconds'],
            setup_and_collection_seconds=r['setup_and_collection_seconds'],model_delta=r['model_parameter_delta_l2'],
            policy_delta=r['policy_max_abs_delta'],checks=r['checks'],groups=groups[n])
        if com2:
            result['arms'][n]['task_loss_calibration']=r['task_loss_calibration']
            result['arms'][n]['task_weight']=r['task_weight']
        if failure_replay:
            result['arms'][n]['failure_replay']=r['failure_replay']
            result['arms'][n]['priority_selected_windows']=r['priority_selected_windows']
    for key,l in groups['control'].items():
        rr=groups[candidate][key]
        result['differences'][key]=dict(return_mae_ratio=rr['return_mae']/max(l['return_mae'],1e-9),
            real_rows_match=l['rows']==rr['rows'],real_failures_difference=rr['real_failures']-l['real_failures'],
            missed_failure_fraction_change=rr['missed_failure_fraction']-l['missed_failure_fraction'])
    result['candidate_for_actor_test']=(right['checks'][-1]['metrics']['h8']['state_nse']<.8*left['checks'][-1]['metrics']['h8']['state_nse']
        and all(result['differences'][f'{mode}/closed_loop/h32/perturbed_loco']['return_mae_ratio']<.8 for mode in ['noisy','deterministic']))
    if com2:
        result['candidate_for_actor_test']=(right['checks'][-1]['metrics']['h8']['state_nse']<=1.1*left['checks'][-1]['metrics']['h8']['state_nse']
            and all(result['differences'][f'{mode}/closed_loop/h32/perturbed_loco']['return_mae_ratio']<=.85 for mode in ['noisy','deterministic']))
        if right.get('task_gradient_ratio',0):
            assert left['calibration_seeds']==right['calibration_seeds']==[984103,984104]
            assert abs(right['task_loss_calibration']['auxiliary_to_state_gradient_norm']-.5)<1e-5
            result['gate']='Prospective v2 short-rollout gate; v1 original32tick rejection remains unchanged.'
            result['candidate_for_actor_test']=(right['checks'][-1]['metrics']['h8']['state_nse']<=1.1*left['checks'][-1]['metrics']['h8']['state_nse']
                and all(result['differences'][f'{mode}/closed_loop/h8/perturbed_loco']['return_mae_ratio']<=.75
                        and result['differences'][f'{mode}/closed_loop/h32/perturbed_loco']['return_mae_ratio']<=1.05
                        for mode in ['noisy','deterministic']))
    if failure_replay:
        assert left['calibration_seeds']==right['calibration_seeds']==[984105,984106]
        assert left['priority_selected_windows']==0 and right['priority_selected_windows']==160*right['optimizer_steps']
        assert left['failure_replay']['qualifying_training_windows']==right['failure_replay']['qualifying_training_windows']
        result['kind']='verified_failure_replay_prediction_comparison'
        result['candidate_for_actor_test']=(right['checks'][-1]['metrics']['h8']['state_nse']<=1.1*left['checks'][-1]['metrics']['h8']['state_nse']
            and all(result['differences'][f'{mode}/closed_loop/h8/perturbed_loco']['return_mae_ratio']<=.75
                    and result['differences'][f'{mode}/closed_loop/h32/perturbed_loco']['return_mae_ratio']<=1.05
                    and result['differences'][f'{mode}/closed_loop/h32/normal_loco']['return_mae_ratio']<=1.1
                    for mode in ['noisy','deterministic']))
    (folder/('verified-failure-replay.json' if failure_replay else 'verified-com2.json' if com2 else 'verified-rwm.json')).write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in ['arms','differences']},indent=2))
    for n,r in result['arms'].items():
        print(n,json.dumps({k:v for k,v in r.items() if k not in ['checks','groups']}))
        print('final_state_check',json.dumps(r['checks'][-1]))
        for mode in ['noisy','deterministic']:
            for h in [8,32]:print(n,mode,h,json.dumps(r['groups'][f'{mode}/closed_loop/h{h}/perturbed_loco']))


if __name__=='__main__':main(sys.argv[1],com2='--com2' in sys.argv[2:],failure_replay='--failure-replay' in sys.argv[2:])
