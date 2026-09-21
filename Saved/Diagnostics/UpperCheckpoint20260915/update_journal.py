import json
from pathlib import Path
root=Path(__file__).resolve().parents[3]
contract=json.loads((root/'Content/locomotion/NN/prophecy_upper_body_runtime.json').read_text())
p=root/'ProjectJournal.md'
text=p.read_text(encoding='utf-8-sig')
lines=text.splitlines()
for i,line in enumerate(lines):
    if line.startswith('- Accepted Upper checkpoint:'):
        lines[i]=f"- Accepted Upper checkpoint (user-selected 2026-09-15): `{contract['checkpoint_path']}`, step `{contract['checkpoint_step']:,}`, SHA-256 `{contract['checkpoint_sha256']}`. Supersedes the August-16 checkpoint; this is the accepted selection, not a claim of best quality."
    if line.startswith('- Upper ONNX:'):
        lines[i]=f"- Upper ONNX: `Content/locomotion/NN/prophecy_upper_body_b100.onnx`, SHA-256 `{contract['onnx_sha256']}`; runtime contract: `Content/locomotion/NN/prophecy_upper_body_runtime.json`; exporter: `Tools/NN/ExportProphecyUpperBodyPolicy.py` (default updated to the selected September-15 checkpoint)."
entry='- Upper checkpoint replacement (2026-09-15): user selected the sole checkpoint in run 20260915_102838_ik_upper_cached_ae1ae4_bs64_allk32_ble_h66961999d3, latest_download2.pt, step 76,750. Installed exported ONNX and matching startup-audit contract at existing runtime paths; exporter default updated. Input/output 281/90, batch100, all non-provenance/runtime geometry contract fields unchanged. ONNX reference output versus PyTorch max absolute error 2.384185791015625e-7. Previous installed model/contract backed up in Saved/Diagnostics/UpperCheckpoint20260915/previous. No lower/attack checkpoint, Blueprint or scene edits; no engine build/restart. Evidence and short PIE result in Saved/Diagnostics/UpperCheckpoint20260915.'
lines[2:2]=[entry,'']
p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
