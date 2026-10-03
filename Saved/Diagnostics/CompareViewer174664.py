from pathlib import Path
import json,numpy as np
source=Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs/20260922_latest_chained_variants/best_total_172k175k_20260924/seed_2026092211/complete')
stage=Path('Saved/Slash174664')
a=np.load(source/'rollout.npz');b=np.load(stage/'chain/complete/rollout.npz')
report={k:float(np.max(np.abs(a[k]-b[k]))) for k in ('positions','rotations','frame_targets')}
report['segments_identical']=json.loads((source/'manifest.json').read_text())['segments']==json.loads((stage/'chain/complete/manifest.json').read_text())['segments']
report['source_frames']=len(a['positions']);print(report)
assert report['segments_identical'] and max(report[k] for k in ('positions','rotations','frame_targets'))<1e-5
(stage/'viewer_reference_comparison.json').write_text(json.dumps(report,indent=2)+'\n')
