import pathlib,json,hashlib,shutil,subprocess
root=pathlib.Path(__file__).resolve().parents[3]
stepper=pathlib.Path('C:/Users/singerie/Documents/Cursor/stepper')
manifest=root/'Tools/Recovery/NNCheckpoints20261003.json'
data=json.loads(manifest.read_text())
for name in ('dodge','parry'):
 contract='Content/locomotion/NN/defense/'+name+'_checkpoint.json'
 meta=json.loads((root/contract).read_text())
 source=pathlib.Path(meta['file']);sha=hashlib.sha256(source.read_bytes()).hexdigest()
 assert sha==meta['sha256'],source
 if any(r['sha256']==sha for r in data['checkpoints']):continue
 dest=root/'Tools/Recovery/Checkpoints'/f'{name}_step_{meta["step"]}-{sha[:12]}.pt'
 if not dest.exists():shutil.copy2(source,dest)
 assert hashlib.sha256(dest.read_bytes()).hexdigest()==sha
 data['checkpoints'].append(dict(path=dest.relative_to(root).as_posix(),sha256=sha,bytes=dest.stat().st_size,
  contracts=[contract],sources=[dict(original_path=str(source),restore_root='stepper',restore_path=source.relative_to(stepper).as_posix())]))
data['updated']='2026-10-06'
manifest.write_text(json.dumps(data,indent=2)+'\n')
paths=[]
for directory in (root/'Saved/Diagnostics').glob('*20261006'):
 for f in directory.iterdir():
  if not f.is_file() or f.stat().st_size>256*1024:continue
  if f.suffix.lower() not in {'.py','.ps1','.json','.txt','.log'}:continue
  if f.name.startswith('editor'):continue
  paths.append(f.relative_to(root).as_posix())
for name in ('Defense20261005','Parry1149700-20261006'):
 directory=root/'Saved/DefenseIntegration/CheckpointUpdates'/name
 for f in directory.iterdir():
  if f.is_file() and f.stat().st_size<1024*1024 and f.suffix.lower() in {'.py','.json','.log'}:
   paths.append(f.relative_to(root).as_posix())
paths.extend(['Content/_mygame/SKM_UEFN_Mannequin.uasset','Content/locomotion/NN/defense/parry_checkpoint.json'])
paths.extend(f.relative_to(root).as_posix() for f in (root/'Content/_mygame/Materials/LimbColors').glob('*.uasset'))
subprocess.run(['git','add','-f','--',*paths],cwd=root,check=True)
print(json.dumps({'curated_files':len(paths),'checkpoint_count':len(data['checkpoints']),'checkpoint_bytes':sum(x['bytes'] for x in data['checkpoints'])}))
