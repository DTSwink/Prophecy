"""Graph-cache invalidation audit; no inference, processes or file mutations."""
import json
from pathlib import Path
from unittest.mock import patch
import nn_worker as worker

base = worker.policy_graph_fingerprint()
source = worker.inspect.getsource(worker.PolicyStep)
original = Path.read_bytes

def changed(path, target):
    data = original(path)
    return data+b'\n# audit-only edit\n' if path.resolve() == target.resolve() else data

checks = []
with patch.object(Path, 'read_bytes', lambda path: changed(path, Path(worker.__file__))):
    assert worker.policy_graph_fingerprint() == base
    checks.append('Resume/diagnostic edits do not invalidate the compiled policy')
with patch.object(worker.inspect, 'getsource', return_value=source.replace('torch.zeros(1, 2)', 'torch.ones(1, 2)')):
    assert worker.policy_graph_fingerprint() != base
    checks.append('Policy-step changes invalidate the compiled policy')
for target in [Path(worker.lower_ctl.__file__), worker.MODEL_ROOT/'models/provenance.json']:
    with patch.object(Path, 'read_bytes', lambda path: changed(path, target)):
        assert worker.policy_graph_fingerprint() != base
    checks.append(target.name+' changes invalidate the compiled policy')
with patch.object(worker.torch, '__version__', 'different-runtime'):
    assert worker.policy_graph_fingerprint() != base
    checks.append('Torch runtime changes invalidate the compiled policy')
print(json.dumps(dict(passed=True, checks=checks)))
