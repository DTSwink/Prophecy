"""Install only an exported checkpoint that has passed the native chain audit."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone

p=argparse.ArgumentParser()
p.add_argument('staging',type=Path)
a=p.parse_args()
root=Path(__file__).resolve().parents[2]
staging=a.staging.resolve()
contract=json.loads((staging/'prophecy_slash_native.json').read_text())
runtime=json.loads((staging/'prophecy_slash_runtime.json').read_text())
audit=json.loads((staging/'unreal_chain_audit.json').read_text())
assert audit['passed'], 'Native replay did not pass; live models unchanged'
assert contract['checkpoint_sha256']==runtime['checkpoint_sha256']
files=['prophecy_slash_native.json','prophecy_slash_runtime.json']
for net in contract['networks'].values():
    path=staging/net['file']
    assert path.parent==staging and hashlib.sha256(path.read_bytes()).hexdigest()==net['sha256']
    files.append(path.name)
dest=root/'Content/locomotion/NN'
backup=root/'Saved/CheckpointBackups'/datetime.now(timezone.utc).strftime(f'%Y%m%d-%H%M%S-before-{runtime["checkpoint_step"]}')
backup.mkdir(parents=True,exist_ok=False)
for path in dest.glob('prophecy_slash_*'):
    if path.is_file():shutil.copy2(path,backup/path.name)
for name in files:shutil.copy2(staging/name,dest/name)
receipt=dict(checkpoint_sha256=runtime['checkpoint_sha256'],checkpoint_step=runtime['checkpoint_step'],
    backup=str(backup),installed=files,native_audit=str(staging/'unreal_chain_audit.json'))
(staging/'installation_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
