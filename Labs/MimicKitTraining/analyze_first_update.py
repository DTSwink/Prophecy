"""Separate first-rollout reproducibility from update-size effects."""
import json
from pathlib import Path
import torch
torch.set_num_threads(1)
root=Path('/workspace/mimickit_trial/causal_regression')
folders=[root/'cp150_stock_seed9018_repeat_a',root/'cp150_stock_seed9018_repeat_b',root/'cp150_frozen_seed9018_repeat_c']
def load(p): return torch.load(p,map_location='cpu',weights_only=True)
first_initial=load(folders[0]/'initial_trace.pt')
first_rollout=load(folders[0]/'rollout_trace.pt')
reports=[]
for folder in folders:
    initial=load(folder/'initial_trace.pt');rollout=load(folder/'rollout_trace.pt')
    report=dict(name=folder.name,initial_equal={k:bool(torch.equal(first_initial[k],v)) for k,v in initial.items()},
        optimizer=json.loads((folder/'training.json').read_text())['records'][0],
        rollout={})
    for key in ['obs','action','reward','a_logp','sample_permutation']:
        lhs=first_rollout[key];rhs=rollout[key];delta=(lhs-rhs).abs()
        entry=dict(bit_identical=bool(torch.equal(lhs,rhs)),max_abs_difference=float(delta.max()))
        if key!='sample_permutation':
            dims=tuple(range(1,delta.ndim));per=delta.amax(dims)
            changed=(per>0).nonzero().flatten()
            entry['first_different_step']=int(changed[0]) if len(changed) else None
            entry['first_step_max_difference']=float(per[0])
        report['rollout'][key]=entry
    reports.append(report)
(root/'first_update_reproducibility.json').write_text(json.dumps(reports,indent=2))
print(json.dumps(reports,indent=2))
