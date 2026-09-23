import json,numpy as np
from pathlib import Path
rows=[]
for line in (Path(__file__).parents[1]/'Logs/GameAnimationSample3.log').open(errors='replace'):
    if 'SlashReturnAudit,' not in line:continue
    fields=line.strip().split('SlashReturnAudit,')[1].split(',')
    if not fields[0].startswith('BP_'):continue
    vals=list(map(float,fields[1:]));r={'agent':fields[0]}
    r.update(zip(['elapsed','dt','step','alpha','width'],vals[:5]))
    for i,name in enumerate(['route','neutral','nn','blend','clear','solved','shoulder']):r[name]=vals[5+i*3:8+i*3]
    r['lengths']=vals[26:28]
    if len(vals)>28:r['fixed_speed']=vals[28]
    rows.append(r)
Path(__file__).with_suffix('.json').write_text(json.dumps(rows,indent=2))
shown=[r for r in rows if 'fixed_speed' in r] or rows
for r in shown[:14]:
    print('tick',round(r['elapsed']*60),'step',round(r['step'],3),'alpha',round(r['alpha'],3),
          'route',np.round(r['route'],2),'neutral',np.round(r['neutral'],2),
          'clear_delta',round(np.linalg.norm(np.array(r['clear'])-r['blend']),3),
          'reach_delta',round(np.linalg.norm(np.array(r['solved'])-r['clear']),3),'fixed_speed',r.get('fixed_speed'),'lengths',r['lengths'])
