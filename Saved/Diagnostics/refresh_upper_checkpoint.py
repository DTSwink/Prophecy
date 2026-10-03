import datetime,hashlib,json,pathlib,shutil,subprocess,sys
root=pathlib.Path(__file__).resolve().parents[2]
source_dir=pathlib.Path(r'C:\Users\singerie\Documents\Cursor\stepper\training\runs\20261001_121128_ik_upper_cached_ae1ae4_bs64_allk32_blend_noise50_initgaze50each\checkpoints')
source=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else max(source_dir.glob('*.pt'),key=lambda p:p.stat().st_mtime_ns)
assert source.is_file(),source
stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
backup=root/'Saved/CheckpointBackups'/f'{stamp}-UpperBeforeRefresh'
stage=root/'Saved/Diagnostics'/f'UpperCheckpoint-{stamp}'
backup.mkdir(parents=True);stage.mkdir(parents=True)
live=root/'Content/locomotion/NN'
names=['prophecy_upper_body_b100.onnx','prophecy_upper_body_runtime.json']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest().upper()
previous={}
for n in names:
    previous[n]=sha(live/n);shutil.copy2(live/n,backup/n)
    assert sha(backup/n)==previous[n]
frozen=stage/'source_checkpoint.pt'
source_hash=sha(source);shutil.copy2(source,frozen)
assert source_hash==sha(frozen)==sha(source),'Training save changed during copy; retry from a complete save'
old=json.loads((live/names[1]).read_text())
subprocess.run([sys.executable,str(root/'Tools/NN/ExportProphecyUpperBodyPolicy.py'),'--checkpoint',str(frozen),'--output-dir',str(stage),'--reference-clip',old['reference_clip_path']],check=True)
new=json.loads((stage/names[1]).read_text())
metadata={'checkpoint_path','checkpoint_sha256','checkpoint_step','checkpoint_kind','onnx_path','onnx_sha256','startup_audit'}
changes=[k for k in old.keys()|new.keys() if k not in metadata and old.get(k)!=new.get(k)]
assert not changes,f'Runtime contract changed: {changes}'
new['onnx_path']=str(live/names[0])
(stage/names[1]).write_text(json.dumps(new,indent=2)+'\n')
for n in names:
    assert sha(live/n)==previous[n],'Installed files changed during export; preserve newer edits'
for n in names:
    shutil.copy2(stage/n,live/n)
    assert sha(stage/n)==sha(live/n)
receipt=dict(source=str(source),source_sha256=source_hash,checkpoint_step=new['checkpoint_step'],backup=str(backup),stage=str(stage),previous=previous,installed={n:sha(live/n) for n in names},contract_changes=changes)
(backup/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
(root/'Saved/Diagnostics/latest_upper_install.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
