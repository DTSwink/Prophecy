import json,pathlib,math
p=pathlib.Path(__file__).parent
capture=json.loads((p/'TimeGaitVerified.json').read_text())
assert not capture['error'],capture['error']
rows=[r for r in capture['rows'] if r['name'].endswith('_C_1') and r['time']>=1.49]
trace=[r for r in map(json.loads,(p/'TimeGaitVerified.jsonl').read_text().splitlines()) if r['actor'].endswith('_C_1') and r['time']>=1.49]
summary=dict(samples=len(rows),speed_min=min(r['speed'] for r in rows),speed_max=max(r['speed'] for r in rows),cube_xy_max=max(math.hypot(*r['cube_delta'][:2]) for r in rows),walk_only=all(r['walk_policy'] and r['walk_weight']==1 for r in trace),nn_next_root_min=min(r['lower_input'][121] for r in trace),nn_next_root_max=max(r['lower_input'][121] for r in trace))
assert summary['speed_min']>999.9 and summary['speed_max']<1000.1
assert summary['cube_xy_max']<.004 and summary['walk_only']
assert summary['nn_next_root_max']-summary['nn_next_root_min']<.0001
(p/'TimeGaitVerifiedSummary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
