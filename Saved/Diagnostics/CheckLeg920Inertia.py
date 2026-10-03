import json,numpy as np
from pathlib import Path
p=Path('Saved/Diagnostics/Leg920InertiaOff-same-frame.json')
if not p.exists():print('Capture still running');raise SystemExit
x=json.loads(p.read_text());b=x['before'];a=x['after']
def pos(d,n):return np.array(d[n]['target']['p'])
def geom(d):
 h,k,f=[pos(d,n+'_r') for n in ('thigh','calf','foot')];u=k-h;v=f-k
 return {'bend':float(np.degrees(np.arccos(np.clip(np.dot(u,v)/np.linalg.norm(u)/np.linalg.norm(v),-1,1)))),'lengths':[float(np.linalg.norm(u)),float(np.linalg.norm(v))],'reach':float(np.linalg.norm(f-h))}
g=geom(a);dist=float(np.linalg.norm(pos(a,'foot_r')-pos(b,'thigh_r')))
print('DISABLE',x['ok'],'before',geom(b),'after',g)
print('corrected hip to original foot',dist,'available reach',sum(g['lengths']),'excess',dist-sum(g['lengths']))
print('pelvis correction',pos(b,'pelvis')-pos(a,'pelvis'),'hip correction',pos(b,'thigh_r')-pos(a,'thigh_r'),'foot correction',pos(b,'foot_r')-pos(a,'foot_r'))
baseline=json.loads(Path('Saved/Diagnostics/Leg920-capture.json').read_text())['rows'];test=json.loads(Path('Saved/Diagnostics/Leg920InertiaOff-capture.json').read_text())['rows']
baseline={r['clock']:r for r in baseline}
err=max(np.linalg.norm(np.array(r['targets'][n][kind]['p'])-baseline[r['clock']]['targets'][n][kind]['p']) for r in test if r['clock']<=920 for n in r['targets'] for kind in ('previous','future','target'))
print('max prefix position difference',err)
