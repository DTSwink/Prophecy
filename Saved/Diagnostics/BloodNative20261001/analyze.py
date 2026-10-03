import json,statistics
from pathlib import Path
p=Path(__file__).parent
d=json.loads((p/'experiment.json').read_text(encoding='utf-8-sig'))
out={k:d[k] for k in ('success','error')}
out['emitters']=[]
for system in d['niagara_assets']:
 for e in system['emitters']:
  functions=sorted({f for s in e.get('scripts',[]) for f in s['external_calls'] if any(x in f.lower() for x in ('collision','query','export','storeparticle'))})
  interfaces=sorted({i['class'] for s in e.get('scripts',[]) for i in s['data_interfaces'] if any(x in i['class'].lower() for x in ('collision','query','export'))})
  out['emitters'].append(dict(system=system['asset'],name=e['name'],enabled=e['enabled'],target=e.get('target'),calls=functions,interfaces=interfaces))
out['timings']=[]
for trial in d.get('query_timings',[]):
 n=trial['rays_per_sample'];a=statistics.median(trial['ue_ms']);b=statistics.median(trial['jolt_ms'])
 out['timings'].append(dict(bodies=trial['bodies'],ue_ms_per_1000_rays=a*1000/n,jolt_ms_per_1000_rays=b*1000/n,jolt_divided_by_ue=b/a,ue_samples_ms=trial['ue_ms'],jolt_samples_ms=trial['jolt_ms']))
out['isolation']={k:v for k,v in d.items() if any(x in k for x in ('without_proxies','channel_filter','channel_policy'))}
(p/'summary.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
