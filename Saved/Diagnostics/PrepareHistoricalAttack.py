from pathlib import Path
import json,hashlib,subprocess,shutil
root=Path.cwd();stage=root/'Saved/CheckpointBackups/20260922-234039-before-123793';base=root/'Content/locomotion/NN'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
old=json.loads((stage/'prophecy_slash_runtime.json').read_text(encoding='utf-8'));now=json.loads((base/'prophecy_slash_runtime.json').read_text(encoding='utf-8'))
native=json.loads((stage/'prophecy_slash_native.json').read_text(encoding='utf-8'))
expected='6a76321d6e1525c9e6bcfcedcd0ce46676b03dd15dd277c2bd87f6c834239072'
assert old['checkpoint_sha256']==native['checkpoint_sha256']==sha(Path(old['checkpoint_path']))==expected
for rev in ['f314e8d','8919c05']:
 exporter=subprocess.check_output(['git','show',rev+':Tools/NN/ExportProphecySlashPolicy.py']).decode('utf-8')
 assert expected in exporter and 'done slash 2 2/checkpoints/good.pt' in exporter
for key in ('input_dim','output_dim','root_position_m','root_rotation','bone_names','attack_labels','post_hit_tail_steps','gate_threshold'):
 assert old[key]==now[key],key
files=['prophecy_slash_runtime.json','prophecy_slash_native.json']
for net in native['networks'].values():
 assert sha(stage/net['file'])==net['sha256'],net['file']
 files.append(net['file'])
print('verified historical',old['checkpoint_step'],expected,'schema',old.get('transition_schema','legacy frozen'))
current_native=json.loads((base/'prophecy_slash_native.json').read_text(encoding='utf-8'))
print('native differing fields',[k for k in set(native)|set(current_native) if native.get(k)!=current_native.get(k)])
dest=base/'AttackSeptember20';dest.mkdir(exist_ok=True)
before={str(p):sha(p) for d in (base,base/'Attack160664',base/'Attack184064') for p in d.glob('prophecy_slash_*') if p.is_file()}
for name in files:shutil.copy2(stage/name,dest/name)
assert all(sha(Path(p))==v for p,v in before.items())
receipt=dict(checkpoint_path=old['checkpoint_path'],checkpoint_sha256=expected,step=old['checkpoint_step'],historical_commits=['f314e8d','8919c05'],backup=str(stage),files={n:sha(dest/n) for n in files},existing_unchanged=True)
(root/'Saved/Diagnostics/AttackSeptember20-installation.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print('installed',len(files),'files',sum((dest/n).stat().st_size for n in files))
