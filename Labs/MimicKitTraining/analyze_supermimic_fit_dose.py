"""Check paired model-fit results; forecast gains are not policy-learning gains."""
import json
import math
from pathlib import Path
import sys


def analyze(folder,heads=False,capacity=False):
    folder=Path(folder);arms={}
    assert not(heads and capacity)
    candidates=([('width1024',256),('width2048',256)] if capacity else
                [('coupled',256),('detached',256)] if heads else [('batch256',256),('batch2048',2048)])
    for name,batch in candidates:
        r=json.loads((folder/name/'result.json').read_text())
        assert r['complete'] and r['batch_size']==batch and r['fit_window']==8
        assert r['policy_parameter_delta_l2']==0 and r['actor_updates']==0
        skipped=bool(r.get('skip_fit_reason'))
        assert r['world_model_parameter_delta_l2']==0 if skipped else r['world_model_parameter_delta_l2']>0
        assert r['transitions']==262144
        if heads:
            assert r['head_fit_mode']==name and len(r['auxiliary_gradient_audit']['records'])==3
            assert skipped==(not r['auxiliary_gradient_audit']['fit_gate'])
        if capacity:
            assert r['capacity_audit']['width']==int(name[5:])
            assert r['capacity_audit']['function_preserving']
            assert r['capacity_audit']['initial_prediction_max_abs']<=2e-5
        assert r['data_seed']==84731 and r['provenance']['training_seed']==84731
        assert r['provenance']['model_pretraining_accounting']
        assert r['provenance']['setup_and_baseline_seconds']>0
        log=(folder/(name+'.log')).read_text()
        if not skipped:assert 'GRAPH_FIT_VERIFIED 0 ' in log and 'GRAPH_FIT_VERIFIED 1 ' in log
        for c in r['checks']:
            assert c['nominal_transition_predictions']==c['steps']*batch*8
            for mode in ['replay_actions','policy_actions']:
                for horizon in ['h1','h8','h32']:
                    for scope in ['all','perturbed_loco']:
                        q=c[mode][horizon][scope];assert q['rows']>=32
                        assert all(math.isfinite(q[k]) and q[k]>=0 for k in ['state_nse','next_action_rmse'])
        assert r['checks'][0]['steps']==0
        assert r['checks'][-1]['steps']==0 if skipped else r['checks'][-1]['steps']>=2
        arms[name]=r
    a,b=arms.values()
    for key in ['dataset_sha256','validation_sha256']:assert a[key]==b[key]
    for key in ['checkpoint_sha256','warm_model']:assert a['provenance'][key]==b['provenance'][key]
    if heads:assert a['auxiliary_gradient_audit']==b['auxiliary_gradient_audit']
    for mode in ['replay_actions','policy_actions']:
        if not capacity:assert a['checks'][0][mode]==b['checks'][0][mode]
        else:
            for horizon in ['h1','h8','h32']:
                for scope in ['all','perturbed_loco']:
                    left,right=[r['checks'][0][mode][horizon][scope] for r in (a,b)]
                    assert left['rows']==right['rows']
                    for key in ['state_nse','next_action_rmse']:
                        assert math.isclose(left[key],right[key],rel_tol=.002,abs_tol=2e-6),(mode,horizon,scope,key,left[key],right[key])
    result=dict(verified=True,policy_learning_claim=False,
        limitation='One fixed policy/model and fresh replay seed. Select model-fit hypotheses only; require real policy learning and matched-time PPO comparison before promotion.',
        dataset_sha256=a['dataset_sha256'],validation_sha256=a['validation_sha256'],arms={})
    for name,r in arms.items():
        result['arms'][name]={k:r[k] for k in ['fit_seconds','total_audit_seconds','collection_or_wait_seconds','checks','world_model_sha256']}
        result['arms'][name]['setup_seconds']=r['provenance']['setup_and_baseline_seconds']
        result['arms'][name]['reused_preparation']=r['provenance']['model_pretraining_accounting']
        if heads:
            result['arms'][name]['auxiliary_gradient_audit']=r['auxiliary_gradient_audit']
            result['arms'][name]['skip_fit_reason']=r.get('skip_fit_reason')
        if capacity:result['arms'][name]['capacity_audit']=r['capacity_audit']
        first,last=r['checks'][0],r['checks'][-1]
        result['arms'][name]['final_to_initial_ratio']={mode:{h:{k:last[mode][h]['perturbed_loco'][k]/first[mode][h]['perturbed_loco'][k]
            for k in ['state_nse','next_action_rmse']} for h in ['h1','h8','h32']} for mode in ['replay_actions','policy_actions']}
    if capacity:
        assert b['capacity_audit']['dynamics_parameters']>3*a['capacity_audit']['dynamics_parameters']
        left,right=[r['checks'][-1]['policy_actions']['h32']['perturbed_loco'] for r in (a,b)]
        gap=abs(a['fit_seconds']-b['fit_seconds'])
        ratios={k:right[k]/left[k] for k in ['state_nse','next_action_rmse']}
        matched=gap<=max(5.,.05*min(a['fit_seconds'],b['fit_seconds']))
        result['capacity_gate']=dict(matched_fit_time=matched,fit_time_gap_seconds=gap,
            wide_to_narrow_h32_ratio=ratios,
            passed=matched and ratios['next_action_rmse']<=.85 and ratios['state_nse']<=1.,
            rule='Consider another actor test only for >=15% lower closed-loop H32 action error without worse state error at matched fit time; model accuracy alone is not a policy-learning win.')
    (folder/('verified-capacity.json' if capacity else 'verified-head-fit.json' if heads else 'verified-fit-dose.json')).write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2));return result


if __name__=='__main__':analyze(sys.argv[1],heads='--heads' in sys.argv[2:],capacity='--capacity' in sys.argv[2:])
