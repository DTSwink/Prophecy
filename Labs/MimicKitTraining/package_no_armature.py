"""Package the current verified UEFN runtime for a no-armature continuation.

The input checkpoint/source archive stays immutable. Current engine adapters
must travel together; copying only the engine would omit required runtime files.
"""
from pathlib import Path
import hashlib,json,shutil,zipfile
from uefn_package import runtime_files,verify_package
ROOT=Path(__file__).resolve().parents[2]
out=ROOT/'Saved/MimicKitNoArmature';out.mkdir(exist_ok=True)
source=ROOT/'Saved/MimicKitOmniRun/resume-source.zip'
assert hashlib.sha256(source.read_bytes()).hexdigest()=='be1a4ceb5b90f5de3ee05b19d764e1b1a4a4c4d5a8f8dc2bc4e28613a5c74a00'
changes={}
replacements=runtime_files(ROOT)
with zipfile.ZipFile(source) as old,zipfile.ZipFile(out/'source.zip','w',zipfile.ZIP_DEFLATED) as new:
    for entry in old.infolist():
        body=old.read(entry.filename)
        if entry.filename in replacements:
            body=replacements[entry.filename].read_bytes()
            changes[entry.filename]=hashlib.sha256(body).hexdigest()
        new.writestr(entry,body)
    for name,path in replacements.items():
        if name not in changes:
            body=path.read_bytes();new.writestr(name,body)
            changes[name]=hashlib.sha256(body).hexdigest()
with zipfile.ZipFile(out/'source.zip') as check:verify_package(check,ROOT)
for name in ('omni-calibration.json','geometry.json'):
    shutil.copyfile(ROOT/'Saved/MimicKitOmniRun'/name,out/name)
receipt=json.loads((ROOT/'Saved/MimicKitOmniRun/download-latest-receipt.json').read_text())
assert hashlib.sha256(Path(receipt['local_path']).read_bytes()).hexdigest()==receipt['sha256']
(out/'input-checkpoint.json').write_text(json.dumps(receipt,indent=2))
(out/'package.json').write_text(json.dumps(dict(base_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),changed_files=changes),indent=2))
print(json.dumps(dict(changed_files=list(changes),source_bytes=(out/'source.zip').stat().st_size,checkpoint_verified=True)))
