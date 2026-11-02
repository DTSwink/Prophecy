"""Verify frozen-policy planning outcomes; never infer a learning-speed gain."""
import argparse
import json
from pathlib import Path
import numpy as np
from analyze_supermimic_pilots import paired, GROUPS


def analyze(folder):
    folder=Path(folder)
    runs={seed:json.loads((folder/('seed_'+str(seed))/'result.json').read_text()) for seed in [984110,984111]}
    assert len({r['checkpoint_sha256'] for r in runs.values()})==1
    assert len({r['gpu'] for r in runs.values()})==1
    result=dict(kind='verified_native_planning_teacher_screen',seeds={},pooled={},
                limitation='Per-state residual planning, not a learned policy. Planning selects using first32ticks; outcome evaluation lasts120ticks. Fresh exploration tests robustness, not independent policy-training replication.')
    for seed,r in runs.items():
        assert r['complete'] and r['actor_updates']==0 and r['policy_max_abs_delta']==0
        assert r['reset_max_abs_error']<2e-4
        assert r['planning_horizon']==32 and r['residual_ticks']==8
        assert len(r['planning'])==16 and {(p['round'],p['candidate']) for p in r['planning']}=={(i,j) for i in range(2) for j in range(8)}
        item={k:r[k] for k in ['setup_seconds','planning_seconds','total_seconds','selected_residual_rms','selected_zero_fraction','reset_max_abs_error']}
        for mode,ev in r['evaluations'].items():
            item[mode]=paired(ev['control'],ev['planned'],'perturbed_loco')
        result['seeds'][seed]=item
    for mode in ['deterministic','noisy']:
        pooled={arm:dict(rows=[runs[s]['evaluations'][mode][arm]['rows'][0] for s in runs]) for arm in ['control','planned']}
        groups={g:paired(pooled['control'],pooled['planned'],g) for g in GROUPS}
        post={}
        for arm,ev in pooled.items():
            late_returns=[];late_failures=[]
            for row in ev['rows']:
                selected=np.array(row['row_group'])==2
                late_returns.extend(np.array(row['row_post32_return'])[selected].tolist())
                late_failures.extend(np.array(row['row_post32_failure'])[selected].tolist())
            post[arm]=dict(mean_post32_return=float(np.mean(late_returns)),post32_failures=int(sum(late_failures)),
                           cohort_size=len(late_returns),note='Whole initial cohort; early-dead rows contribute zero after32. Interpret with total failures, never as conditional late success.')
        result['pooled'][mode]=dict(groups=groups,post32=post)
    noisy=result['pooled']['noisy']['groups']['perturbed_loco']
    det=result['pooled']['deterministic']['groups']['perturbed_loco']
    result['candidate_for_distillation_and_matched_ppo_race']=bool(
        noisy['failure_change_percentage_points']<=-2 and noisy['return_change_motion_cluster_interval_95'][0]>0
        and det['failure_change_percentage_points']<=1
        and all(v['noisy']['failure_change_percentage_points']<=0 for v in result['seeds'].values()))
    (folder/'verified-planning.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2));return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder');analyze(p.parse_args().folder)
