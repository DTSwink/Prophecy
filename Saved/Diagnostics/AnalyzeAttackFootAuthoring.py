import json,pathlib,math
p=pathlib.Path('Saved/Diagnostics')
d=json.loads((p/'FootAuthoringLive.json').read_text());assert not d['error'],d['error']
perf=json.loads((p/'AttackPerformance/foot_authoring_live.json').read_text())['rows']
for case in range(4):
 rows=[r for r in d['rows'] if r['case']==case]
 transitions=[(r['offset'],r['owners']) for i,r in enumerate(rows) if i==0 or r['owners']!=rows[i-1]['owners']]
 print('case',case,'owners',transitions)
 for before,after in zip(rows,rows[1:]):
  assert all(not b or a for a,b in zip(before['owners'],after['owners'])),(before,after)
 assert all(math.isfinite(x) for r in rows for f in r['feet'] for x in f)
 release=next(r['offset'] for r in rows if not any(r['owners']))
 for label,group in [('pending',[r for r in rows if 4<=r['offset']<25 and any(r['owners'])]),('released',[r for r in rows if release+4<=r['offset']<54 and r['attack']!='None'])]:
  matched=[min(perf,key=lambda p:abs(p['time']-r['time'])) for r in group]
  assert all(abs(p['time']-r['time'])<.02 for p,r in zip(matched,group))
  calls=sum(p['networks'].get('152_b100_gpu',{}).get('calls',0) for p in matched)
  print(label,len(group),'lower calls',calls)
  if label=='released':assert group and calls==0,(case,calls)
  elif group:assert calls>0
 print('walk weights',min(r['weights'][0] for r in rows[:25]),max(r['weights'][0] for r in rows[:25]))
print('FOOT_AUTHORING_ANALYSIS_PASSED')
