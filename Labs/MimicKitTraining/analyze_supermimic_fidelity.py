"""Verify fixed-policy advice against actual simulator counterfactuals."""
import json
from pathlib import Path
import sys
import numpy as np


def analyze(folder):
    folder=Path(folder);summary=dict(arms={},policy_learning_claim=False,
        limitation='Two reset seeds, two ages, one original policy/model; local action probes are not policy-learning gains.')
    cp_hashes=set();model_hashes=set()
    for arm in ['deterministic','noisy']:
        r=json.loads((folder/arm/'result.json').read_text())
        p=json.loads((folder/arm/'provenance.json').read_text())
        assert r['complete'] and r['policy_parameter_delta_l2']==0 and r['actor_updates']==0
        assert r['context_captured_before_rollout'] and r['exploration']==(arm=='noisy')
        assert len(r['checks'])==4 and len(r['probes'])==16
        cp_hashes.add(p['checkpoint_sha256']);model_hashes.add(p['warm_model']['sha256'])
        for c in r['checks']:
            a=c['modes']['anchored']
            assert a['reward_max_error']<=.002 and a['actor_mean_max_error']<=.002 and a['hard_failure_mismatches']==0
            assert all(np.isfinite(v) for v in a['gradient_norms'].values())
        pools={};common={}
        for q in r['probes']:
            key=(q['seed'],q['prefix_ticks']);mask=np.asarray(q['row_valid'],bool)
            assert mask.sum()==q['rows'] and q['rows']>=32
            signature=(mask.tolist(),q['initial_observation_sha256'])
            if key in common:assert common[key]==signature
            else:common[key]=signature
            data={k:np.asarray(q['row_'+k],float)[mask] for k in
                  ['return_delta','short_return_delta','first_reward_delta','predicted_linear_change','failure_delta','motion']}
            assert all(np.isfinite(v).all() for v in data.values())
            pools.setdefault(q['component'],[]).append(data)
        result=dict(seconds=r['seconds'],world_model_quality=r['checks'],components={},
                    reused_preparation=p['model_pretraining_accounting'])
        for component,parts in pools.items():
            d={k:np.concatenate([a[k] for a in parts]) for k in parts[0]}
            motion=d['motion'];groups=np.unique(motion);rng=np.random.default_rng(81297)
            fields=['return_delta','short_return_delta','first_reward_delta','failure_delta']
            means=[]
            for _ in range(1000):
                ids=np.concatenate([np.flatnonzero(motion==g) for g in rng.choice(groups,len(groups),replace=True)])
                means.append([d[k][ids].mean() for k in fields])
            ci=np.quantile(means,[.025,.975],axis=0)
            measured=d['first_reward_delta'] if component=='anchored_h1_dense' else d['short_return_delta']
            predicted=d['predicted_linear_change']
            correlation=(float(np.corrcoef(measured,predicted)[0,1])
                         if measured.std()>0 and predicted.std()>0 else None)
            result['components'][component]=dict(rows=len(motion),
                means={k:float(d[k].mean()) for k in fields},
                mean_intervals_95={k:ci[:,i].tolist() for i,k in enumerate(fields)},
                positive_local_fraction=float((measured>0).mean()),
                positive_full_episode_fraction=float((d['return_delta']>0).mean()),
                predicted_linear_change_mean=float(predicted.mean()),
                predicted_to_local_change_correlation=correlation)
        summary['arms'][arm]=result
    assert len(cp_hashes)==len(model_hashes)==1
    summary.update(checkpoint_sha256=cp_hashes.pop(),world_model_sha256=model_hashes.pop())
    (folder/'verified-fidelity.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2));return summary


if __name__=='__main__':analyze(sys.argv[1])
