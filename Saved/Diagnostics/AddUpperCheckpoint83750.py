"""Freeze, export, validate and install the explicitly requested picker addition."""
import datetime
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

import numpy as np
from onnx.reference import ReferenceEvaluator

root = pathlib.Path(__file__).resolve().parents[2]
source = pathlib.Path(r'C:\Users\singerie\Documents\Cursor\stepper\training\runs\20261001_223123_ik_upper_cached_ae1ae4_bs64_allk32_blend_noise50_initgaze50each_handvelbound\checkpoints\checkpoint_step_083750.pt')
live = root / 'Content/locomotion/NN'
destination = live / 'Upper83750'
assert source.is_file(), source
assert not destination.exists(), f'Preserve existing destination: {destination}'
stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
stage = root / 'Saved/Diagnostics' / f'UpperCheckpoint83750-{stamp}'
stage.mkdir(parents=True)
names = ['prophecy_upper_body_b100.onnx', 'prophecy_upper_body_runtime.json']

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()

preserved = {str((live / folder / name).relative_to(root)): sha(live / folder / name)
             for folder in ['', 'Upper82500', 'Upper85750', 'Upper86750'] for name in names}
frozen = stage / 'source_checkpoint.pt'
source_hash = sha(source)
shutil.copy2(source, frozen)
assert source_hash == sha(frozen) == sha(source), 'Source changed during copy'
old = json.loads((live / names[1]).read_text(encoding='utf-8'))
subprocess.run([sys.executable, '-X', 'utf8', str(root / 'Tools/NN/ExportProphecyUpperBodyPolicy.py'),
                '--checkpoint', str(frozen), '--output-dir', str(stage),
                '--reference-clip', old['reference_clip_path']], check=True)
new = json.loads((stage / names[1]).read_text(encoding='utf-8'))
assert new['checkpoint_step'] == 83750, new['checkpoint_step']
metadata = {'checkpoint_path', 'checkpoint_sha256', 'checkpoint_step', 'checkpoint_kind',
            'onnx_path', 'onnx_sha256', 'startup_audit'}
changes = [key for key in old.keys() | new.keys() if key not in metadata and old.get(key) != new.get(key)]
assert not changes, f'Runtime contract changed: {changes}'
assert new['checkpoint_sha256'] == source_hash
assert new['onnx_sha256'] == sha(stage / names[0])
session = ReferenceEvaluator(str(stage / names[0]))
audit = new['startup_audit']
inputs = np.repeat(np.asarray(audit['input'], dtype=np.float32)[None], new['batch_size'], axis=0)
outputs = session.run(None, {'controller_input': inputs})[0]
assert outputs.shape == (100, 90) and np.isfinite(outputs).all()
error = float(np.abs(outputs - np.asarray(audit['expected_output'], dtype=np.float32)).max())
assert error <= audit['maximum_absolute_error'], error
for path, expected in preserved.items():
    assert sha(root / path) == expected, f'Existing picker pair changed: {path}'
new['onnx_path'] = str(destination / names[0])
(stage / names[1]).write_text(json.dumps(new, indent=2) + '\n', encoding='utf-8')
destination.mkdir()
for name in names:
    shutil.copy2(stage / name, destination / name)
    assert sha(stage / name) == sha(destination / name)
receipt = dict(source=str(source), source_sha256=source_hash, checkpoint_step=83750,
               stage=str(stage), destination=str(destination), contract_changes=changes,
               parity_backend='ONNX ReferenceEvaluator',
               startup_audit_max_absolute_error=error, preserved=preserved,
               installed={name: sha(destination / name) for name in names})
(stage / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
(root / 'Saved/Diagnostics/upper_picker_83750_install.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
print(json.dumps(receipt, indent=2), flush=True)
