import json, shutil
from pathlib import Path
import numpy as np
from onnx.reference import ReferenceEvaluator

root = Path(__file__).resolve().parents[3]
folder = Path(__file__).parent
target = root / 'Content/locomotion/NN'
name = 'prophecy_upper_body_runtime.json'
old = json.loads((target / name).read_text())
new = json.loads((folder / 'staged' / name).read_text())
metadata = {'checkpoint_path','checkpoint_sha256','checkpoint_step','checkpoint_kind','onnx_path','onnx_sha256','startup_audit'}
changes = [k for k in old.keys() | new.keys() if k not in metadata and old.get(k) != new.get(k)]
assert not changes, changes
session = ReferenceEvaluator(str(folder/'staged/prophecy_upper_body_b100.onnx'))
x = np.tile(np.asarray(new['startup_audit']['input'], dtype=np.float32), (100,1))
y = session.run(None, {'controller_input':x})[0]
error = float(np.max(np.abs(y - np.asarray(new['startup_audit']['expected_output'], dtype=np.float32))))
assert np.isfinite(y).all() and error < 1e-3, error
backup = folder/'previous'
backup.mkdir(exist_ok=True)
for file in ['prophecy_upper_body_b100.onnx', name]:
    assert not (backup/file).exists(), 'Backup already exists; do not overwrite'
    shutil.copy2(target/file, backup/file)
new['onnx_path'] = str(target/'prophecy_upper_body_b100.onnx')
shutil.copy2(folder/'staged/prophecy_upper_body_b100.onnx', target/'prophecy_upper_body_b100.onnx')
(target/name).write_text(json.dumps(new, indent=2)+'\n')
report = {'step':new['checkpoint_step'],'checkpoint':new['checkpoint_path'],'sha256':new['checkpoint_sha256'],'onnx_sha256':new['onnx_sha256'],'onnx_max_absolute_error':error,'runtime_contract_changes':changes}
(folder/'installation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
