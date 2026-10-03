import json
from pathlib import Path
r=json.loads(Path('Saved/Diagnostics/Hover260.json').read_text())['rows']
for x in r:
 if 257<=x['tick']<=275:
  print(x['tick'], 'targetZ', [round(t['p'][2],3) for t in x['targets']['foot_l']], 'meshZ',[(m['name'],round(m['feet'][0]['p'][2],3)) for m in x['meshes']],x['pin'].split('raw_pinning:')[1].split('sample_time')[0])
n=[json.loads(l) for l in Path('Saved/Diagnostics/Hover260-nn.jsonl').read_text().splitlines()]
print('KEYS',n[0].keys())
for x in n:
 if x['actor']==r[0]['actor'] and 255<=round(x['time']*60)<=277:
  print('NN',round(x['time']*60), 'inputZ',round(x['lower_input'][11]*100,4),'deltaZ', round(x['lower_delta'][11]*100,4),'predZ',round((x['lower_input'][11]+x['lower_delta'][11])*100,4),'publishedZ',round(x['published_lower'][11]*100,4),'previousZ',round(x['previous_lower'][11]*100,4))
