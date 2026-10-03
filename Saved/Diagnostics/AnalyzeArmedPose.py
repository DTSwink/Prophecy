import json
from pathlib import Path
p=Path('Saved/Diagnostics/ArmedPose')
d=json.loads((p/'live.json').read_text())
assert not d['error'],d['error']
rows=d['rows'];perf=json.loads(Path('Saved/Diagnostics/AttackPerformance/manual_armed_pose.json').read_text())['rows']
out=dict(events=d['events'],initial_degrees=rows[0]['distance'],held_max_degrees=max(r['distance'] for r in rows if 100<=r['n']<=120),resumed_degrees=next(r['distance'] for r in rows if r['n']==155),windows={})
for name,lo,hi in [('manual',40,120),('normal_after_stop',130,150),('manual_restarted',205,220),('real_half_attack',230,250)]:
 t0=next(r['time'] for r in rows if r['n']==lo);t1=next(r['time'] for r in rows if r['n']==hi)
 rr=[r for r in perf if t0<=r['time']<=t1]
 nets={k:sum(r['networks'].get(k,{}).get('calls',0) for r in rr) for k in {k for r in rr for k in r['networks']}}
 out['windows'][name]=dict(frames=len(rr),network_calls=nets)
(p/'analysis.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
