"""Validate frozen calibration and pool descriptive counts, not learning gains."""
import argparse
import json
from pathlib import Path


def analyze(folder,termination=False):
    folder=Path(folder);out=dict(arms={},limitation='Overlapping branch cohorts are correlated. These are descriptive model-calibration measurements, not independent learning replications or a speedup.')
    for name in (['analytic','learned'] if termination else ['initial','final']):
        r=json.loads((folder/name/'result.json').read_text())
        assert r['complete'] and r['actor_updates']==0 and r['policy_max_abs_delta']==r['world_max_abs_delta']==0
        assert len(r['runs'])==4 and {x['seed'] for x in r['runs']}=={683101,683102}
        assert r['world_sha256']=='5486d850e231c9fbb2ef44538e9f23d89698789abfd2771f72581bba33aa0fcf'
        if termination:
            assert r['failure_mode']==name and r['policy']=='final'
            assert r['policy_file_sha256']=='f8dd4d32bbe0d31557c53c92d2299e6af5ea8128949568aa15dbf0f1ff70b2e1'
        item=dict(total_seconds=r['total_seconds'],setup_seconds=r['setup_seconds'],groups={})
        for noisy in [False,True]:
            for closed in [False,True]:
                for horizon in r['horizons']:
                    for group in ['normal_loco','normal_idle','perturbed_loco','perturbed_idle']:
                        rows=[]
                        for run in r['runs']:
                            assert run['validation']['score_max_error']<.002 and run['validation']['hard_event_mismatches']==0
                            if run['exploration']!=noisy:continue
                            rows += [p['groups'][group] for p in run['predictions'] if p['closed_loop']==closed and p['horizon']==horizon]
                        n=sum(x['rows'] for x in rows)
                        if not n:continue
                        summary={k:sum(x.get(k,0) for x in rows) for k in ['rows','real_failures','predicted_failures','false_positive','false_negative']}
                        keys=['real_return','predicted_return','return_mae']
                        if termination:keys+=['expected_failure_percent','failure_brier_score','expected_return_mae']
                        for key in keys:
                            summary[key]=sum(x.get(key,0)*x['rows'] for x in rows)/n
                        for key in ['real_failures','predicted_failures','false_positive','false_negative']:
                            summary[key+'_percent']=100*summary[key]/n
                        observed=sum(x['real_alive_for_state_error'] for x in rows)
                        summary['state_nse_real_alive']=sum(x.get('state_nse_real_alive',0)*x['real_alive_for_state_error'] for x in rows)/max(observed,1)
                        key=f'{"noisy" if noisy else "deterministic"}/{"closed_loop" if closed else "logged_controls"}/h{horizon}/{group}'
                        item['groups'][key]=summary
        out['arms'][name]=item
    if termination:
        comparisons={}
        for mode in ['noisy','deterministic']:
            key=f'{mode}/closed_loop/h32/perturbed_loco'
            a=out['arms']['analytic']['groups'][key];b=out['arms']['learned']['groups'][key]
            comparisons[mode]=dict(brier_ratio=b['failure_brier_score']/max(1e-9,a['failure_brier_score']),
                expected_return_mae_ratio=b['expected_return_mae']/max(1e-9,a['expected_return_mae']),
                real_failures_difference=b['real_failures']-a['real_failures'],rows_difference=b['rows']-a['rows'])
        out['termination_comparison']=comparisons
        out['candidate_for_actor_test']=all(v['brier_ratio']<.85 and v['expected_return_mae_ratio']<.85 for v in comparisons.values())
    (folder/'verified-calibration.json').write_text(json.dumps(out,indent=2))
    for name,item in out['arms'].items():
        print(name,'seconds',round(item['total_seconds'],2))
        for key,value in item['groups'].items():
            if key.startswith('noisy/closed_loop/') and key.endswith('/perturbed_loco'):
                print(key,json.dumps(value))
    if termination:print(json.dumps(dict(comparison=comparisons,candidate_for_actor_test=out['candidate_for_actor_test'])))
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder');p.add_argument('--termination',action='store_true');a=p.parse_args();analyze(a.folder,a.termination)
