"""Fresh, cached and interrupted graph paths under fast inference execution."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import nn_worker as worker
from directional_nn import configure_direction, generate_command

owner = configure_direction(worker.ResumeLocomotion('run'), 'run', 'backward')
request = dict(kind='direction', policy='run', gait='run', direction='backward',
               duration=.1, phase=.2, rootYawSpeed=0, rootYawStart=0, rootYawStop=None,
               verifyReference=True)
with tempfile.TemporaryDirectory(prefix='footik-graph-build-') as folder:
    with patch.object(worker, 'ROOT', Path(folder)), worker.inference_execution():
        fresh = generate_command(owner, request)
        artifact = next((Path(folder)/'.nn-cache').glob('*.pt'))
        assert hasattr(worker.torch.jit.load(str(artifact)), 'forward')
        owner.steps.clear()
        cached = generate_command(owner, request)
        artifact.write_bytes(b'interrupted disposable graph')
        owner.steps.clear()
        repaired = generate_command(owner, request)
        for other in (cached, repaired):
            for channel in ('poses', 'roots', 'pins'):
                assert fresh[channel] == other[channel], channel
        assert max(x['referenceError'] for x in (fresh, cached, repaired)) < 2e-6
        result = dict(passed=True, poses=len(fresh['poses']),
                      referenceError=fresh['referenceError'],
                      checks=['fresh graph has forward under fast execution',
                              'original controller agrees on every policy step',
                              'cached load preserves exact poses/roots/pins',
                              'interrupted graph rebuild preserves exact output'])
(worker.ROOT/'snapshots/graph-build-verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result))
