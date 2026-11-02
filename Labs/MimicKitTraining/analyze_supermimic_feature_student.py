import argparse
import json
from pathlib import Path
from analyze_supermimic_pilots import paired,GROUPS


def analyze(folder):
    folder=Path(folder);runs={k:json.loads((folder/k/'result.json').read_text()) for k in ['ppo','features']}
    assert all(r['complete'] for r in runs.values())
    assert len({r['teacher_data_sha256'] for r in runs.values()})==1
    candidate=runs['features'];assert candidate['original_parameter_max_abs_delta']==0 and candidate['head_parameter_delta_l2']>0
    result=dict(kind='verified_frozen_feature_student',comparison={},fit=candidate['fit'],
        accounting={a:{k:r[k] for k in ['reused_teacher_collection_seconds','reused_source_worker_seconds','source_control_learning_seconds','fit_or_load_seconds','evaluation_seconds','total_worker_seconds']} for a,r in runs.items()},
        limitation='One teacher/training seed reused. Two evaluation cohorts are not independent training replications. No fresh end-to-end speed claim.')
    passes=[];pooled={a:{'rows':[]} for a in runs}
    for cohort in ['existing','fresh']:
        result['comparison'][cohort]={}
        for mode in ['deterministic','noisy']:
            p,c=[runs[a]['evaluations'][cohort][mode] for a in ['ppo','features']]
            result['comparison'][cohort][mode]={g:paired(p,c,g) for g in GROUPS}
        n=result['comparison'][cohort]['noisy'];d=result['comparison'][cohort]['deterministic']
        passes.append(n['perturbed_loco']['failure_change_percentage_points']<=-1 and d['perturbed_loco']['failure_change_percentage_points']<=1
                      and all(x['normal_loco']['failure_change_percentage_points']<=1 for x in [n,d]))
        for a in runs:pooled[a]['rows']+=runs[a]['evaluations'][cohort]['noisy']['rows']
    result['pooled_noisy']=paired(pooled['ppo'],pooled['features'],'perturbed_loco')
    charged=candidate['reused_teacher_collection_seconds']+candidate['fit_or_load_seconds']
    result['charged_collection_and_fitting_seconds']=charged
    result['candidate_for_independent_confirmation']=bool(all(passes) and result['pooled_noisy']['return_change_motion_cluster_interval_95'][0]>0
                                                         and charged<=candidate['source_control_learning_seconds']+5)
    (folder/'verified-features.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder');analyze(p.parse_args().folder)
