from pathlib import Path
import json,shutil
src=Path('Saved/SlashTrain2223');dst=Path('Saved/SlashTrain2223Flat');dst.mkdir(exist_ok=True)
for p in src.glob('*.onnx'):shutil.copy2(p,dst/p.name)
for n in ['prophecy_slash_native.json','prophecy_slash_runtime.json']:shutil.copy2(src/n,dst/n)
g=json.loads((src/'source_native_geometry.json').read_text());height=g['root_position'][1];g['root_position'][1]=0
f=json.loads((src/'chain_audit.json').read_text())
for x in f['inputs']:x[263]-=height
for key in ['expected','four_step_oracle']:
 for x in f[key]:
  for b in range(25):x[132+b*3]-=height
for b in range(25):g['startup_expected'][132+b*3]-=height
(dst/'source_native_geometry.json').write_text(json.dumps(g));(dst/'chain_audit.json').write_text(json.dumps(f))
print('flattened reference native origin by',height,'m')
