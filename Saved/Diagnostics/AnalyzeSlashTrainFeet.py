import json
from pathlib import Path
import numpy as np

folder=Path('Saved/Diagnostics')
def load(label):
    data=json.loads((folder/f'SlashTrainFeet-{label}.json').read_text())
    assert data['reason']=='Complete',data['reason']
    return {r['tick']:r for r in data['rows']}
old=load('baseline');late=load('late147')
prefix=max(np.max(np.abs(np.array(old[t]['targets'][b]['future']['p'])-late[t]['targets'][b]['future']['p']))
           for t in range(30,148) for b in old[t]['targets'])
print('Prefix through147 maximum position difference cm:',prefix)
assert prefix<1e-6,prefix
for bone in ('pelvis','foot_l','foot_r'):
    for name,rows in [('before',old),('late fix',late)]:
        cached=np.array(rows[149]['targets'][bone]['previous']['p'])-rows[148]['targets'][bone]['future']['p']
        displayed=np.array(rows[149]['targets'][bone]['target']['p'])-rows[148]['targets'][bone]['target']['p']
        print(name,bone,'cached frame shift',np.linalg.norm(cached),'displayed step',np.linalg.norm(displayed))
        if name=='late fix':assert np.linalg.norm(cached)<1e-4,(bone,cached)
