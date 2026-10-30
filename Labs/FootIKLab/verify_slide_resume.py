"""Single-thread native NN restart parity; no live viewer or state writes."""
import os
for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[key] = '1'
os.environ['CUDA_VISIBLE_DEVICES'] = ''
import json, time
from pathlib import Path
from nn_worker import ResumeLocomotion
from directional_nn import configure_direction
from surface_nn import Stream

root = Path(__file__).resolve().parent
folder = root.parent.parent/'Saved/FootIKSlideTransitions20261029'
started = time.perf_counter()
owner = ResumeLocomotion('run')
configure_direction(owner, 'run', 'left')
initial = json.loads((folder/'initial-request.json').read_text())
request = json.loads((folder/'resume-request.json').read_text())
assert request['reset'] and len(request['seeds']) == 2
retained = Stream(owner)
retained.step(initial)
before = retained.checkpoint()
actual = retained.step(request)
fresh = Stream(owner)
expected = fresh.step(request)
assert actual == expected, 'Reset must encode new current/history exactly like a fresh NN stream'
assert retained.checkpoint()['tensors'] == fresh.checkpoint()['tensors']
assert retained.checkpoint()['tensors'] != before['tensors'], 'Old recurrent state must be replaced'
report = dict(passed=True, nativeResetExact=True, seconds=time.perf_counter()-started)
(folder/'native-resume.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report))
