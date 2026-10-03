import json, math
from pathlib import Path
root=Path(__file__).parent
live=json.loads((root/'SpecialRecoveryLive-20260923-154645.json').read_text())
assert live['error'] is None
summary={'live_defenses':[], 'attack_regression':{}}
for ep in range(4):
    rows=[r for r in live['rows'] if r['episode']==ep]
    states=sorted(set(r['state'] for r in rows))
    ret=[r for r in rows if r['phase']=='return']
    assert ret and len(ret)>=70
    summary['live_defenses'].append({'episode':ep,'states':states,'return_ticks':len(ret),'final_weights':ret[-1]['weights']})
capture=json.loads((root/'CalfRoll-20260923-154715.json').read_text())
assert capture['error'] is None and capture['frames']==600
groups={}
for row in capture['rows']:
    groups.setdefault(row['agent'],[]).append(row)
    assert all(math.isfinite(v) for bone in row['bones'].values() for endpoint in bone for v in endpoint)
for agent,rows in groups.items():
    exits=sum('ATTACKING' in a['state'] and 'LOCOMOTION' in b['state'] for a,b in zip(rows,rows[1:]))
    summary['attack_regression'][agent]={'frames':len(rows),'attack_exits':exits,'states':sorted(set(r['state'] for r in rows))}
(root/'SpecialRecoverySummary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
