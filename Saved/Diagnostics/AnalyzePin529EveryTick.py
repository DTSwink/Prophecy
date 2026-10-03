import json,re
from pathlib import Path
D=Path('Saved/Diagnostics')
a=json.loads((D/'Pin529Baseline.json').read_text())['rows']
p=D/'Pin529EveryTick.json'
if not p.exists():raise SystemExit('Capture not ready')
d=json.loads(p.read_text());b=d['rows'];print('result',d['reason'])
A={r['tick']:r for r in a};B={r['tick']:r for r in b}
def pin(r):return tuple(map(float,re.search(r'effective_pinning: \{x: ([^,]+), y: ([}]+)',r['pin']).groups()))
for n in range(524,540):
 x=A[n];y=B[n]
 print(n,'before',x['pin'].split('effective_pinning:')[1].split('sample_time')[0],'after',y['pin'].split('effective_pinning:')[1].split('sample_time')[0], 'foot',y['targets']['foot_l'][2]['p'])
print('prefix_max',max(sum((x-y)**2 for x,y in zip(A[n]['targets']['foot_l'][1]['p'],B[n]['targets']['foot_l'][1]['p']))**.5 for n in B if n<=527))
for label,rows in [('baseline',A),('tick',B)]:
 print(label,'distances',[(n,round(sum((x-y)**2 for x,y in zip(rows[n]['targets']['foot_l'][2]['p'],rows[n-1]['targets']['foot_l'][2]['p']))**.5,5)) for n in range(526,536)])
