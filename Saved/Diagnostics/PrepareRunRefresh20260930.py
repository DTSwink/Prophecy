import pathlib,hashlib,json,shutil,datetime
root=pathlib.Path(__file__).resolve().parents[2]
stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
work=root/'Saved/Diagnostics'/('RunCheckpoint'+stamp)
backup=root/'Saved/CheckpointBackups'/(stamp+'-RunBeforeRefresh')
work.mkdir();backup.mkdir(parents=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest().upper()
files=['prophecy_lower_body_run_b100.onnx','prophecy_lower_body_runtime.json']
receipt={'backup':str(backup),'work':str(work),'old':{}}
for name in files:
 src=root/'Content/locomotion/NN'/name;dst=backup/name
 before=sha(src);shutil.copy2(src,dst)
 assert before==sha(src)==sha(dst),'Installed model changed while backing up'
 receipt['old'][name]={'sha256':before,'bytes':dst.stat().st_size}
(backup/'manifest.json').write_text(json.dumps(receipt,indent=2))
(backup/'RestoreRun.ps1').write_text("$ErrorActionPreference = 'Stop'\nif (Get-Process UnrealEditor -ErrorAction SilentlyContinue) { throw 'Close Unreal before restoring the Run model.' }\n$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') -Raw | ConvertFrom-Json\n$destination = 'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Content/locomotion/NN'\nforeach ($entry in $manifest.old.PSObject.Properties) {\n    $source = Join-Path $PSScriptRoot $entry.Name\n    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $entry.Value.sha256) { throw 'Backup hash mismatch' }\n}\nforeach ($entry in $manifest.old.PSObject.Properties) { Copy-Item -LiteralPath (Join-Path $PSScriptRoot $entry.Name) -Destination (Join-Path $destination $entry.Name) -Force }\nWrite-Output 'Previous Run model and matching contract restored.'\n")
training=pathlib.Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs/20260927_220308_ik_run_turns_reface_mse0005_20260927_train/checkpoints')
src=max(training.glob('*.pt'),key=lambda p:p.stat().st_mtime_ns)
before=sha(src);shutil.copy2(src,work/'source_checkpoint.pt')
assert before==sha(src)==sha(work/'source_checkpoint.pt'),'Training checkpoint changed while copying; retry snapshot'
receipt['source']={'path':str(src),'sha256':before,'mtime':datetime.datetime.fromtimestamp(src.stat().st_mtime).isoformat()}
(work/'source.json').write_text(json.dumps(receipt,indent=2))
prior=root/'Saved/Diagnostics/RunCheckpoint20260929Refresh'
shutil.copy2(prior/'ValidateExport.py',work/'ValidateExport.py')
(work/'VerifyLoaded.py').write_text((prior/'VerifyLoaded.py').read_text().replace('RunCheckpoint20260929Refresh',work.name))
(root/'Saved/Diagnostics/RunRefreshCurrent.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt,indent=2))
