"""Calibration-only coefficient; independent-seed/world-bootstrap validation."""
import argparse
import json
from pathlib import Path
import numpy as np


def variance(x):
    return np.square(x-x.mean(0)).sum()/len(x)


def coefficient(h,c):
    h=h-h.mean(0);c=c-c.mean(0)
    return float(-(h*c).sum()/max(1e-12,np.square(c).sum()))


def interval(h,c,value):
    rng=np.random.default_rng(738201);ratios=[]
    for _ in range(1000):
        ids=rng.integers(len(h),size=len(h))
        ratios.append(variance(h[ids]+value*c[ids])/max(1e-12,variance(h[ids])))
    return np.quantile(ratios,[.025,.975]).tolist()


def analyze(folder):
    folder=Path(folder);reports={n:json.loads((folder/n/'result.json').read_text()) for n in ['calibration','validation']}
    data={n:np.load(folder/n/'gradient_sketch.npz') for n in reports}
    for n,r in reports.items():
        assert r['complete'] and r['actor_updates']==r['policy_max_abs_delta']==r['world_max_abs_delta']==0
        assert r['native_scoring_validation']['hard_event_mismatches']==0 and r['native_scoring_validation']['score_max_error']<.002
    assert reports['calibration']['seed']==849200 and reports['validation']['seed']==984200
    assert reports['calibration']['world_sha256']==reports['validation']['world_sha256']
    result=dict(kind='heldout_conditional_gradient_variance',branches=[],reports=reports,
       caveat='Frozen64dim motor-head gradient sketch, not fullactor. World bootstrap within each branch; do not pool repeated worlds as independent. Frozen sharedcritic differs from published MFPG-PPO separatecritics. No actortraining/learninggain.',
       timing_caveat='Measured capture includes diagnostic scoring; branch cost includes model5copies and gradient projection. Diagnostic variance-times-cost is not a training-throughput measurement. H8 has no separate timing so no H8 compute gate.')
    for b in [0,24,56,80]:
        for h in [8,32]:
            prefix=f'b{b}_h{h}_';arrays=[]
            for n in reports:
                high=data[n][prefix+'high'].astype(float)
                corr=(data[n][prefix+'coupled']-data[n][prefix+'independent']).astype(float)
                arrays.append((high,corr))
            value=coefficient(*arrays[0]);high,corr=arrays[1]
            ratio=variance(high+value*corr)/variance(high);ci=interval(high,corr,value)
            train_ratio=variance(arrays[0][0]+value*arrays[0][1])/variance(arrays[0][0])
            branch_time=next(x['paired_and_independent_model_seconds'] for x in reports['validation']['branches_report'] if x['branch']==b)
            capture_time=reports['validation']['real_capture_120ticks_seconds']*32/120
            multiplier=1+branch_time/capture_time
            entry=dict(branch=b,horizon=h,calibration_rows=len(arrays[0][0]),validation_rows=len(high),
               coefficient=value,calibration_variance_ratio=train_ratio,heldout_variance_ratio=ratio,
               heldout_world_interval_95=ci,corrector_mean_l2=float(np.linalg.norm(corr.mean(0))),
               real_gradient_mean_l2=float(np.linalg.norm(high.mean(0))),
               diagnostic_compute_multiplier=multiplier if h==32 else None,
               variance_times_diagnostic_cost=ratio*multiplier if h==32 else None,
               followup_training_gate=bool(h==32 and ratio<.8 and ci[1]<1 and ratio*multiplier<.95))
            result['branches'].append(entry)
    result['candidate_for_training_test']=any(x['followup_training_gate'] for x in result['branches'])
    (folder/'verified-multifidelity.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='reports'},indent=2));return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder');analyze(p.parse_args().folder)
