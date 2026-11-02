"""Verify paired model audits; prediction accuracy is not a learning speedup."""
import argparse,json
import numpy as np
from pathlib import Path


def analyze(folder,names=('residual','integrated')):
    assert len(names)==2
    arms={name:json.loads((folder/name/'result.json').read_text()) for name in names}
    for d in arms.values():
        assert d['complete'] and d['actor_updates']==0 and d['policy_parameter_delta_l2']==0
        assert d['fit_seconds']>=d['fit_budget_seconds'] or d.get('early_stop')
    assert len({d['provenance']['checkpoint_sha256'] for d in arms.values()})==1
    paired=arms[names[0]]['dataset_sha256']==arms[names[1]]['dataset_sha256']
    if 'value_weights_sha256' in arms[names[0]]:
        assert arms[names[0]]['value_weights_sha256']==arms[names[1]]['value_weights_sha256']
    if 'direction_pairs_sha256' in arms[names[0]]:
        assert arms[names[0]]['direction_pairs_sha256']==arms[names[1]]['direction_pairs_sha256']
    report=dict(shared_identical_dataset=paired,actor_changed=False,
        limitation='Frozen-policy model diagnostic; this does not demonstrate faster policy learning.',arms={})
    if not paired:
        report['comparison_warning']='Separately simulated datasets differ. Treat as exploratory; repeat with one shared replay before attributing a gain to architecture.'
    for name,d in arms.items():
        final=d['checks'][-1]
        row=dict(fit_seconds=d['fit_seconds'],fit_steps=final['steps'],
                 setup_seconds=d['provenance']['setup_and_baseline_seconds'],
                 data_collection_or_wait_seconds=d['collection_seconds'],
                 h1_state_nse=final['h1']['state_nse'],h8_state_nse=final['h8']['state_nse'],
                 next_action_rmse=final['next_action_rmse'],total_audit_seconds=d['total_audit_seconds'])
        for key in ['h1_critic_rmse','h8_critic_rmse','heldout_directional_change_mse','heldout_directional_target_mse']:
            if key in final:row[key]=final[key]
        if 'value_weight_stats' in d:row['value_weight_stats']=d['value_weight_stats']
        if 'direction_stats' in d:row['direction_stats']=d['direction_stats']
        if d.get('early_stop'):row['early_stop']=d['early_stop']
        gradient=d.get('gradient_audit',{})
        row['exact_scoring_passed']=gradient.get('passed',False)
        row['probes']=[{k:p[k] for k in ['prefix_ticks','amplitude','rows','real_reward_change','predicted_linear_change','positive_fraction']} for p in gradient.get('probes',[])]
        report['arms'][name]=row
    report['common_row_probes']=[]
    a,b=[arms[name].get('gradient_audit',{}).get('probes',[]) for name in names]
    for p,q in zip(a,b):
        assert (p['prefix_ticks'],p['amplitude'])==(q['prefix_ticks'],q['amplitude'])
        mask=np.asarray(p['row_valid'])&np.asarray(q['row_valid'])
        item=dict(prefix_ticks=p['prefix_ticks'],amplitude=p['amplitude'],rows=int(mask.sum()),arms={})
        for name,probe in zip(names,[p,q]):
            v=np.asarray(probe['row_real_delta'])[mask]
            item['arms'][name]=dict(mean_real_change=float(v.mean()),median_real_change=float(np.median(v)),positive_fraction=float((v>0).mean()))
        report['common_row_probes'].append(item)
    (folder/'verified-model-comparison.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('arms',nargs='*',default=['residual','integrated'])
    a=p.parse_args();print(json.dumps(analyze(a.folder,a.arms),indent=2))
