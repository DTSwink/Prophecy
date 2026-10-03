import json, statistics
from pathlib import Path
rows=[]
for mode in ['on','off']:
 for repeat in ['A','B']:
  path=Path(f'Saved/Benchmarks/jolt_hits_contact_{mode}_{repeat}_20260915.json')
  if not path.exists():continue
  report=json.loads(path.read_text(encoding='utf-8-sig'))
  if report['error']:raise RuntimeError((str(path),report['error']))
  case=report['passes'][0]
  hits=case['actual_nn_validation']
  row=dict(mode=mode,repeat=repeat,samples=case['samples'],world=case['world_tick'],
           events=hits['physical_hit_delegates_delivered'],events_per_frame=hits['physical_hits_per_frame'],
           native_floor_lift_cm=case['before']['multi_jolt_handoff']['floor']['contact_benchmark_floor_lift_cm'])
  rows.append(row)
print(json.dumps(rows,indent=2))
if len(rows)==4:
 means={mode:statistics.mean(r['world']['mean_ms'] for r in rows if r['mode']==mode) for mode in ['on','off']}
 delta=means['on']-means['off']
 result=dict(trials=rows,mean_world_ms=means,delta_ms=delta,delta_percent=100*delta/means['off'],
             trial_order=['on_A','off_A','off_B','on_B'],agents=100,warmup_frames=60,measured_frames_per_trial=360,
             note='Controlled contact workload: retained NNJoltCrowd with native floor raised 20 cm. Original setup produced zero solved contacts. Same binary/settings for all four trials; only hit events differ. Minimal native Agent callback included, arbitrary Blueprint handlers excluded.')
 Path('Saved/Benchmarks/JoltHitEventsSummary_20260915.json').write_text(json.dumps(result,indent=2))
 print(json.dumps(dict(means=means,delta_ms=delta,delta_percent=100*delta/means['off'])))
