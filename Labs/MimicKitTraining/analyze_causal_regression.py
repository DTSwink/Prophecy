"""Check controls and paired physical outcomes; no training or inference changes."""
from pathlib import Path
import json
import numpy as np
import torch
ROOT = Path('/workspace/mimickit_trial/causal_regression')
torch.set_num_threads(1)
baseline = np.load(ROOT/'cp150_stock_seed9017/eval_0000_7719.npz')
base_error = baseline['mse'].mean(0)
base_model = torch.load(ROOT/'cp150_stock_seed9017/model_0000.pt', map_location='cpu', weights_only=True)
reports = []
for path in sorted(ROOT.glob('*/eval_*_7719.json')):
    report = json.loads(path.read_text())
    if report['updates'] == 0: continue
    data = np.load(path.with_suffix('.npz'))
    assert np.array_equal(data['initial'], baseline['initial']), f'Unmatched start: {path}'
    assert np.array_equal(data['back'], baseline['back'])
    initial = torch.load(path.parent/'model_0000.pt', map_location='cpu', weights_only=True)
    assert all(torch.equal(initial[k], base_model[k]) for k in initial), 'Different initial policy'
    model = torch.load(path.parent/f"model_{report['updates']:04d}.pt", map_location='cpu', weights_only=True)
    norm_unchanged = all(torch.equal(model[k], initial[k]) for k in initial if k.startswith('_obs_norm.'))
    actor_unchanged = all(torch.equal(model[k], initial[k]) for k in initial if k.startswith('_model._actor') or k.startswith('_model._action_dist'))
    critic_unchanged = all(torch.equal(model[k], initial[k]) for k in initial if k.startswith('_model._critic'))
    if report['branch'].startswith('frozen'): assert norm_unchanged
    if report['branch'] == 'norm_only': assert actor_unchanged and critic_unchanged
    d = data['mse'].mean(0)-base_error
    half = 1.96*d.std(ddof=1)/np.sqrt(d.size)
    report.update(delta_vs_initial=float(d.mean()), paired_approx_95ci=[float(d.mean()-half),float(d.mean()+half)],
        initial_poses_bit_identical=True, normalization_unchanged=norm_unchanged,
        actor_unchanged=actor_unchanged, critic_unchanged=critic_unchanged)
    reports.append(report)
result = dict(baseline_mse=float(base_error.mean()), paired_worlds=int(base_error.size), results=reports,
    limitation='Paired intervals describe 128 matched evaluation starts; training-seed replication is separate.')
(ROOT/'analysis.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
