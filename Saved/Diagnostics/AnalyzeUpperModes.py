import json,statistics as st
from pathlib import Path
p=Path('Saved/Diagnostics/AttackPerformance')
out={}
for mode,ids in [('clip',[0,3]),('checkpoint',[1,2])]:
 runs=[]
 for i in ids:
  f=p/f'upper_{mode}_{i}.json'
  if not f.exists():continue
  rows=json.loads(f.read_text())['rows'];steps=[r for r in rows if r['calls']['lower_input']>0]
  stages={k:st.mean(r['ms'][k] for r in steps) for k in ['layers','attack','upper_input','upper_run','upper_output']}
  total=[sum(r['ms'][k] for k in stages) for r in steps]
  nets={k:dict(ms_per_step=sum(r['networks'].get(k,{}).get('ms',0) for r in steps)/len(steps),calls=sum(r['networks'].get(k,{}).get('calls',0) for r in steps)) for k in {k for r in steps for k in r['networks']}}
  runs.append(dict(frames=len(rows),steps=len(steps),world_ms=st.mean(r['world_ms'] for r in rows),upper_path_mean_ms=st.mean(total),upper_path_median_ms=st.median(total),stages=stages,networks=nets,half_frames=sum(r['half']>0 for r in rows)))
 out[mode]=runs
out['manual_native_math']=json.loads(Path('Saved/Diagnostics/UpperPoseSlerpBenchmark.json').read_text())
(p/'upper_modes_analysis.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
