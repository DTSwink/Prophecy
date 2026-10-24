"""Compare real native -PauseOpticalVerify captures; never edits the images."""
import json
from pathlib import Path
import numpy as np
from PIL import Image

lab = Path(__file__).parent
root = lab / 'Saved/Captures'
original = np.asarray(Image.open(root / 'optical-original.png'))[:, :, :3].astype(int)
menu = np.zeros(original.shape[:2], dtype=bool)
menu[425:780, 75:440] = True
report = {}
for label in ('medium', 'strong'):
    current = np.asarray(Image.open(root / f'optical-{label}.png'))[:, :, :3].astype(int)
    changed = np.max(np.abs(current - original), axis=2) > 1
    report[label] = dict(changed_menu_pixels=int(changed[menu].sum()),
                         changed_outside_menu=int(changed[~menu].sum()))
    assert changed[menu].any(), 'Font variant did not change'
    assert not changed[~menu].any(), 'Changed title, backdrop or decoration'
before = json.loads((lab / 'Resources/pre-optical-user-preset.json').read_text())
after = json.loads((lab / 'Resources/pause.json').read_text())
preserved = [k for k in before if k != 'menu_stroke_strength']
assert all(before[k] == after[k] for k in preserved), 'User setting changed'
report['preserved_user_fields'] = len(preserved)
assert 'OutlineSettings' not in (lab / 'Source/PauseMenuLab/Private/PausePainter.h').read_text()
(root / 'optical-check.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
