import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation

p = Path(__file__).resolve().parent
captures = {name: json.loads((p / (name + '.json')).read_text(encoding='utf8'))
            for name in ('baseline', 'no_owner_sword', 'no_body_self')}
def angle(a, b):
    return float(np.degrees((Rotation.from_quat(a['q']) * Rotation.from_quat(b['q']).inv()).magnitude()))
base = {r['tick']: r for r in captures['baseline']['rows']}
result = {}
for name, capture in captures.items():
    rows = {r['tick']: r for r in capture['rows']}
    result[name] = {
        'reason': capture['reason'],
        'prefix_max_body_difference_degrees': max(angle(row['bodies'][bone]['transform'], base[tick]['bodies'][bone]['transform'])
            for tick, row in rows.items() if 30 <= tick <= 199 for bone in row['bodies']),
        'target_max_difference_200_203_degrees': max(angle(row['targets'][bone]['target'], base[tick]['targets'][bone]['target'])
            for tick, row in rows.items() if 200 <= tick <= 203 for bone in row['targets']),
        'samples': [{
            'tick': tick,
            'hand_error_degrees': angle(rows[tick]['bodies']['hand_r']['transform'], rows[tick]['targets']['hand_r']['target']),
            'forearm_error_degrees': angle(rows[tick]['bodies']['lowerarm_r']['transform'], rows[tick]['targets']['lowerarm_r']['target']),
        } for tick in range(199, 205)],
    }
(p / 'comparison.json').write_text(json.dumps(result, indent=2), encoding='utf8')
print(json.dumps(result, indent=2))
