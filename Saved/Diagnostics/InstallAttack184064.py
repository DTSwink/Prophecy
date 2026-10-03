from pathlib import Path
import hashlib,json,shutil
root=Path(__file__).resolve().parents[2]
stage=root/'Saved/Slash184064';base=root/'Content/locomotion/NN';dest=base/'Attack184064'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=['prophecy_slash_native.json','prophecy_slash_runtime.json','prophecy_slash_cone.onnx','prophecy_slash_lower.onnx','prophecy_slash_upper.onnx']
before={str(p.relative_to(base)):sha(p) for d in (base,base/'Attack160664') for p in (d/n for n in files)}
old=json.loads((base/'prophecy_slash_native.json').read_text());new=json.loads((stage/'prophecy_slash_native.json').read_text())
for key in set(old)|set(new):
 if key not in ('checkpoint_sha256','networks','startup_expected'):
  assert old.get(key)==new.get(key),f'Changed native geometry/contract: {key}'
for key in new['networks']:
 for k in ('input_dim','output_dim'):
  assert old['networks'][key][k]==new['networks'][key][k],(key,k)
 assert sha(stage/new['networks'][key]['file'])==new['networks'][key]['sha256']
rt=json.loads((stage/'prophecy_slash_runtime.json').read_text());current=json.loads((base/'prophecy_slash_runtime.json').read_text())
assert rt['checkpoint_sha256']=='e0759ba5039db0db26f5dd17d58e74b72f1dc092f9f7bf6f54e4a622677f7d7b'
assert sha(Path(rt['checkpoint_path']))==rt['checkpoint_sha256']
for key in ('input_dim','output_dim','transition_schema','root_position_m','root_rotation','bone_names','attack_labels','post_hit_tail_steps'):
 assert rt[key]==current[key],key
dest.mkdir(exist_ok=True)
for n in files:shutil.copy2(stage/n,dest/n)
assert before=={p:sha(base/p) for p in before}
receipt=dict(checkpoint=rt['checkpoint_sha256'],step=rt['checkpoint_step'],files={n:sha(dest/n) for n in files},existing_unchanged=before,native_contract_compatible=True)
(stage/'comparison_installation_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
