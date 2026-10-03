import json,pathlib,numpy as np
p=pathlib.Path('Saved/Diagnostics');rows=json.loads((p/'KneeHistoricalBaseline-capture.json').read_text())['rows'];actor=rows[0]['actor']
metrics=json.loads((p/'KneeHistoricalBaseline-metrics.json').read_text())
traces=[json.loads(l) for l in (p/'KneeHistoricalBaseline-nn.jsonl').read_text(encoding='utf-8').splitlines()]
traces=[r for r in traces if r['actor']==actor]
for tick in [143,145,147,151,153,155,165,171,173,175,176,177,178,179,181,195]:
 r=next(r for r in rows if r['clock']==tick);n=min(traces,key=lambda x:abs(x['time']-r['t']))
 print(tick,'temp',n.get('tempering'),'right',n.get('right_foot_tempering'),'weights',r['weights'])
 for s in ('l','r'):
  m=next(x for x in metrics if x['tick']==tick and x['side']==s and x['kind']=='target')
  print(s,{k:round(m[k],2) for k in ('poleturn','thighturn','radius','yaw','footh')})
