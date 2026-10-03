import json,numpy as np
from pathlib import Path
D=Path('Saved/Diagnostics');base={r['tick']:r for r in json.loads((D/'Pin529Baseline.json').read_text())['rows']};d=json.loads((D/'Pin529ToggleOff.json').read_text());r=next(r for r in d['rows'] if r['tick']==528)
print(d['reason'],'off_restore_error_cm',np.linalg.norm(np.array(r['after_disable'][2]['p'])-base[528]['targets']['foot_l'][2]['p']))
assert np.linalg.norm(np.array(r['after_disable'][2]['p'])-base[528]['targets']['foot_l'][2]['p'])<1e-6
p=Path('Docs/WalkPinningEveryTick.md');s=p.read_text(encoding='utf-8');p.write_text(s+'\nDisable tested with a nonzero intermediate correction at528: the same-pose target immediately matches the original baseline (error <1e-6cm), then the owned test ends normally. Evidence: Pin529ToggleOff.json.\n',encoding='utf-8')
