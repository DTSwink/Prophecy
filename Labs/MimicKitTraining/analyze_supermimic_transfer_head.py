import argparse
import json
from pathlib import Path
from analyze_supermimic_pilots import analyze as analyze_base


def analyze(folder):
    folder=Path(folder);result=analyze_base(folder,['full','heads'])
    for name in ['full','heads']:
        r=json.loads((folder/name/'result.json').read_text());audit=r['output_layer_transfer']
        assert audit['method']==name and audit['head_parameter_delta_l2']>0 and r['training_seed']==849190
        rows=[u['metrics'] for u in r['updates'] if 'actor_loss' in u['metrics']]
        assert len(rows)==audit['updates'] and all(x['transfer_motor_grad_norm']>0 for x in rows)
        assert all([v['seed'] for v in ev['rows']]==[984190,984191] for ev in r['evaluations'])
        if name=='heads':assert audit['feature_max_abs_delta']==0 and audit['trainable_counts']['features']==0
        else:assert audit['feature_max_abs_delta']>0 and audit['trainable_counts']['features']>0
        result['arms'][name]['output_layer_transfer']=audit
    n=result['comparisons']['noisy']['groups'];d=result['comparisons']['deterministic']['groups']
    own=result['arms']['heads']['noisy']['groups']['perturbed_loco']
    result['candidate_for_independent_native_ppo_confirmation']=bool(result['comparison_timing']['approximately_matched']
        and own['failure_change_percentage_points']<=-1
        and n['perturbed_loco']['failure_change_percentage_points']<=-2
        and n['perturbed_loco']['return_change_motion_cluster_interval_95'][0]>0
        and d['perturbed_loco']['failure_change_percentage_points']<=1
        and all(x['normal_loco']['failure_change_percentage_points']<=1 for x in [n,d]))
    result['limitation']='Short final-layer versus full-actor model-gradient screen. Prior model326.300588s preparation extra; no nativePPO speed claim.120tick normal horizon requires300tick confirmation.'
    (folder/'verified-transfer.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder');analyze(p.parse_args().folder)
