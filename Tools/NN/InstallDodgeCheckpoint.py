"""Export a compatible Dodge fine-tune; optionally install after neural parity checks.

Keeps the accepted geometry, six-bank controls and frozen lower policies unchanged.
The original 198044 fixture remains an immutable port regression reference.
"""
import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from ExportDefenseNetworks import PROJECT, SOURCES, digest, export, ort


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkpoint', type=Path)
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args()
    checkpoint = args.checkpoint.resolve()
    new = torch.load(checkpoint, map_location='cpu', weights_only=False)
    original = torch.load(SOURCES/'dodge_step_198044.pt', map_location='cpu', weights_only=False)
    contracts = ['kind', 'input_dim', 'output_dim', 'bank_contract', 'leg_contract',
                 'bank_names', 'bank_input_contract', 'bank_overrides', 'lower_identities',
                 'lower_runtime', 'foot_floor_contract', 'root_contract']
    for key in contracts:
        if repr(new[key]) != repr(original[key]):
            raise ValueError(f'{key} changed: requires a runtime compatibility review')
    if new['model'].keys() != original['model'].keys():
        raise ValueError('Network state layout changed')
    for key, value in new['model'].items():
        if value.shape != original['model'][key].shape or not torch.isfinite(value).all():
            raise ValueError(f'Invalid shape/weights: {key}')
        if not key.startswith('upper.') and not torch.equal(value, original['model'][key]):
            raise ValueError(f'Frozen lower policy changed: {key}')
    folder = PROJECT/'Saved/DefenseIntegration/CheckpointUpdates'/f'{new["step"]}_{datetime.now():%Y%m%d_%H%M%S}'
    folder.mkdir(parents=True)
    weights_file = folder/'weights.npz'
    np.savez(weights_file, **{k: v.numpy() for k, v in new['model'].items()})
    model_file = folder/'prophecy_dodge_upper.onnx'
    with np.load(weights_file) as weights:
        assert export(weights, 'upper.trunk', 'upper.delta_head', model_file) == (362, 112)
    options = ort.SessionOptions()
    options.intra_op_num_threads = options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(model_file), sess_options=options, providers=['CPUExecutionProvider'])
    torch.set_num_threads(1)
    weights = new['model']
    def expected(x):
        for i in (0, 3):
            x = F.linear(x, weights[f'upper.trunk.{i}.weight'], weights[f'upper.trunk.{i}.bias'])
            x = F.layer_norm(x, (x.shape[-1],), weights[f'upper.trunk.{i+1}.weight'], weights[f'upper.trunk.{i+1}.bias'], eps=1e-5)
            x = F.gelu(x, approximate='none')
        return F.linear(x, weights['upper.delta_head.weight'], weights['upper.delta_head.bias'])
    inputs = []
    with np.load(SOURCES/'dodge_unreal_reference/reference/trace.npz') as trace:
        inputs += [trace[k].astype(np.float32) for k in trace.files if k.endswith('/upper/input/0')]
    rng = np.random.default_rng(205525)
    inputs += [rng.standard_normal((batch, 362), dtype=np.float32) for batch in (1, 4, 17)]
    errors = []
    with torch.inference_mode():
        for x in inputs:
            actual = session.run(None, {'input': x})[0]
            reference = expected(torch.from_numpy(x)).numpy()
            np.testing.assert_allclose(actual, reference, atol=1e-5, rtol=1e-5)
            errors.append(float(np.max(np.abs(actual-reference))))
    report = dict(checkpoint=str(checkpoint), checkpoint_sha256=digest(checkpoint), step=int(new['step']),
                  onnx_sha256=digest(model_file), input_dim=362, output_dim=112,
                  frozen_lower_unchanged=True, contracts_checked=contracts,
                  parity_batches=len(inputs), parity_max_abs_error=max(errors), installed=False)
    destination = PROJECT/'Content/locomotion/NN/defense'
    if args.install:
        target = destination/model_file.name
        shutil.copy2(target, folder/'previous_prophecy_dodge_upper.onnx')
        report['previous_onnx_sha256'] = digest(target)
        metadata = destination/'dodge_checkpoint.json'
        if metadata.exists():
            shutil.copy2(metadata, folder/'previous_dodge_checkpoint.json')
        shutil.copy2(model_file, target)
        report['installed'] = True
        report['installed_file'] = str(target)
        report['backup_folder'] = str(folder)
        metadata.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    (folder/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
