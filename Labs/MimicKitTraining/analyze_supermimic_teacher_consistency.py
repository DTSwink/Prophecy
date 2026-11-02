"""Analyze repeated searches without mistaking planning for policy learning."""
import argparse,json
from pathlib import Path
import numpy as np
from analyze_supermimic_pilots import paired


def analyze(folder):
    folder=Path(folder);reports=[json.loads((folder/f'seed_{s}'/'result.json').read_text()) for s in [984220,984221]]
    result=dict(cohorts=[],pooled={},followup_distillation_gate=True,
                limitation='Frozen per-state planning, no learned-policy improvement. Two search pools per state; averaging can mix distinct valid strategies. Motion-cluster intervals describe evaluation variation, not across-training-seed reproducibility.')
    assert len({r['checkpoint_sha256'] for r in reports})==1
    for report in reports:
        assert report['complete'] and report['policy_max_abs_delta']==report['actor_updates']==0
        assert report['reset_max_abs_error']<2e-4
        data=np.load(folder/f"seed_{report['seed']}"/'teacher_consistency.npz')
        scope=data['groups']==2
        selection={key:float(np.mean(data[key][scope]-data['score_zero'][scope])) for key in ['score_a','score_b','score_mean']}
        assert min(selection['score_a'],selection['score_b'])>=-1e-5
        entry=dict(seed=report['seed'],consistency=report['consistency'],mean_planning_advantage=selection,
                   planning_seconds=report['planning_seconds'],total_seconds=report['total_seconds'],comparisons={})
        if 'zero_repeat_scores' in data:
            repeated=data['zero_repeat_scores'][:,scope]
            spread=repeated.std(0,ddof=1)
            traces=report['zero_repeat_diagnostics']
            failures=np.array([t['failed'] for t in traces])[:,scope]
            entry['repeat_noise']=dict(score_mean_abs_delta_from_first=float(np.mean(np.abs(repeated[1:]-repeated[0]))),
                score_max_abs_delta_from_first=float(np.max(np.abs(repeated[1:]-repeated[0]))),
                worlds_with_changed_failure=int(np.any(failures!=failures[:1],axis=0).sum()),
                winner_a_advantage_below_three_repeat_stds_fraction=float(np.mean(data['score_a'][scope]-data['score_zero'][scope]<3*spread)),
                obs_first_five_tick_maxima=[t['obs_max_by_tick'][:5] for t in traces],
                action_first_five_tick_maxima=[t['action_max_by_tick'][:5] for t in traces],
                caveat='Three repeats only; descriptive numeric-noise estimate, not a confidence bound. Later full-cohort trace maxima can include different reset episodes.')
        for mode in ['deterministic','noisy']:
            ev=report['evaluations'][mode]
            entry['comparisons'][mode]={name:paired(ev['control'],ev[name],'perturbed_loco') for name in ['winner_a','winner_b','mean']}
        mean=entry['comparisons']['noisy']['mean']
        gate=mean['failure_change_percentage_points']<=-1 and mean['return_change_motion_cluster_interval_95'][0]>0
        entry['gate']=gate;result['followup_distillation_gate'] &= gate
        result['cohorts'].append(entry)
    for mode in ['deterministic','noisy']:
        cohort={name:dict(rows=[row for r in reports for row in r['evaluations'][mode][name]['rows']]) for name in ['control','winner_a','winner_b','mean']}
        result['pooled'][mode]={name:paired(cohort['control'],cohort[name],'perturbed_loco') for name in ['winner_a','winner_b','mean']}
    (folder/'verified-teacher-consistency.json').write_text(json.dumps(result,indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder');print(json.dumps(analyze(p.parse_args().folder),indent=2))
