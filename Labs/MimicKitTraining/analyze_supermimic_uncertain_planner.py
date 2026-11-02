"""Verify physical action-selection outcomes; not a learning-speed claim."""
import argparse
import json
from pathlib import Path
from analyze_supermimic_pilots import paired,GROUPS


def analyze(folder):
    folder=Path(folder);runs={s:json.loads((folder/('seed_'+str(s))/'result.json').read_text()) for s in [984180,984181]}
    assert len({r['checkpoint_sha256'] for r in runs.values()})==1
    assert len({r['gpu'] for r in runs.values()})==1
    assert len({json.dumps(r['calibration'],sort_keys=True) for r in runs.values()})==1
    result=dict(kind='verified_uncertainty_teacher_screen',seeds={},pooled={},calibration=runs[984180]['calibration'],
        limitations='Frozen policy/model, one calibration seed and two new evaluation seeds; not training replications or a learned-policy speedup. Normal rows evaluated120 not300ticks.16fixedcandidate pool differs from prior adaptiveCEM.')
    for s,r in runs.items():
        assert r['complete'] and r['actor_updates']==r['model_updates']==0
        assert r['policy_max_abs_delta']==r['world_max_abs_delta']==0 and r['selection_frozen_before_evaluation']
        assert r['reset_max_abs_error']<2e-4 and r['recurrent_mean_parity_max_abs_error']<1e-6
        assert r['model_sha256']=='0f0c6ca2bc1b53b410350db0b2f8cdd468ae52f3e3bc98fedb9e4c14ee2e0bb9'
        assert r['calibration']['scorer_max_error']<.002 and r['calibration']['hard_event_mismatches']==0
        assert r['candidates']==16 and r['horizon']==32 and r['evaluation_ticks']==120
        item={k:r[k] for k in ['planning_seconds','setup_and_calibration_wait_seconds','total_seconds','prior_model_preparation_seconds','raw_uncertain_same_selection_fraction']}
        for mode,ev in r['evaluations'].items():
            item[mode]={a:paired(ev['control'],ev[a],'perturbed_loco') for a in ['raw','uncertain']}
        result['seeds'][s]=item
    for mode in ['deterministic','noisy']:
        pooled={a:dict(rows=[r['evaluations'][mode][a]['rows'][0] for r in runs.values()]) for a in ['control','raw','uncertain']}
        result['pooled'][mode]={a:{g:paired(pooled['control'],pooled[a],g) for g in GROUPS} for a in ['raw','uncertain']}
        result['pooled'][mode]['uncertain_vs_raw']=paired(pooled['raw'],pooled['uncertain'],'perturbed_loco')
    native=result['calibration']['native_pool_seconds_excluding_audit_estimate']
    result['faster_ranking_than_native_pool']=all(r['planning_seconds']<native for r in runs.values())
    result['candidate_for_distillation_race']={}
    for arm in ['raw','uncertain']:
        n=result['pooled']['noisy'][arm];d=result['pooled']['deterministic'][arm]
        result['candidate_for_distillation_race'][arm]=bool(result['faster_ranking_than_native_pool']
            and n['perturbed_loco']['failure_change_percentage_points']<=-1
            and n['perturbed_loco']['return_change_motion_cluster_interval_95'][0]>0
            and d['perturbed_loco']['failure_change_percentage_points']<=1
            and all(x[g]['failure_change_percentage_points']<=1 for x in [n,d] for g in ['normal_loco','normal_idle','perturbed_idle'])
            and all(r['noisy'][arm]['failure_change_percentage_points']<=0 for r in result['seeds'].values()))
    u=result['pooled']['noisy']['uncertain_vs_raw']
    result['uncertainty_improves_unpenalized_selection']=bool(u['failure_change_percentage_points']<0 and u['return_change_motion_cluster_interval_95'][0]>0)
    (folder/'verified-uncertainty.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder');analyze(p.parse_args().folder)
