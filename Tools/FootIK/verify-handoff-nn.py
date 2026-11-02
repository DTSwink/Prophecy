"""Canonical browser /resume replies and ONNX references for H.prepare.

Run only after the serial native solver sweep is idle. One CPU inference thread,
one directional owner at a time; no HTTP server or persistent helper process.
"""
import importlib.util
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('footik_export', HERE / 'export-nn.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
from directional_nn import resume_in_course

FOLDER = m.PROJECT / 'Saved/Diagnostics/FootIKPort20261030/handoff'
FIXTURES = m.PROJECT / 'Saved/Diagnostics/FootIKPort20261030/NN'


def session(path):
    options = m.ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    return m.ort.InferenceSession(str(path), options, providers=['CPUExecutionProvider'])


@m.torch.inference_mode()
def main():
    manifest = json.loads((FOLDER / 'requests.json').read_text())
    owner = None
    direction = None
    report = []
    for case in manifest['cases']:
        request = json.loads((FOLDER / case['request']).read_text())
        if direction != request['direction']:
            direction = request['direction']
            owner = m.ResumeLocomotion('run')
            m.configure_direction(owner, 'run', direction)
            owner.runtime.install_policy()
            encoder = session(m.OUT / ('run-' + direction + '-seed.onnx'))
            step = session(m.OUT / ('run-' + direction + '-resume.onnx'))
        expected = resume_in_course(owner, request, max_frames=max(152, request['frames']))
        (FOLDER / case['response']).write_text(json.dumps(expected, separators=(',', ':')))
        encoded = encoder.run(None, {'input': m.pack_seed(request['seeds'], request, True).numpy()})[0]
        state, origin = encoded[:, :370], encoded[:, 370:373]
        maximum = {'points': 0., 'axes': 0., 'pins': 0.}
        for i in range(request['frames'] - 1):
            window = dict(roots=request['roots'][i:i + 10], rootYawDegrees=request['rootYawDegrees'][i:i + 10])
            packed = np.concatenate((state, m.pack_window(window).numpy(), origin), -1)
            output = step.run(None, {'input': packed})[0]
            state = output[:, :370]
            for key, data in [('points', output[0, 373:448].reshape(25, 3)), ('axes', output[0, 448:673].reshape(25, 3, 3))]:
                maximum[key] = max(maximum[key], float(np.max(np.abs(data - np.array(expected['poses'][i + 1][key])))))
            maximum['pins'] = max(maximum['pins'], float(np.max(np.abs(output[0, 673:675] - np.array(expected['pins'][i + 1])))))
        fixture = dict(kind='continuation', settings=dict(gait=request['gait'], direction=direction),
                       request=request, expected=expected, tolerance=.0003)
        (FIXTURES / (case['name'] + '-continuation.json')).write_text(json.dumps(fixture, separators=(',', ':')))
        row = dict(name=case['name'], frames=request['frames'], maxAbsoluteError=maximum,
                   passed=max(maximum.values()) <= fixture['tolerance'])
        report.append(row)
        print(json.dumps(row), flush=True)
    (FOLDER / 'python-nn-parity.json').write_text(json.dumps(report, indent=2) + '\n')
    assert all(row['passed'] for row in report), report


if __name__ == '__main__':
    main()
