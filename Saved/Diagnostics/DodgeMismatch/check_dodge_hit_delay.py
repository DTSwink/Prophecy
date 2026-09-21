import json
from pathlib import Path
p=Path('Saved/Diagnostics/DodgeHitDelay/PIE.json')
if not p.exists():print('Capture running');raise SystemExit()
d=json.loads(p.read_text());assert not d['error'],d['error']
episodes=[];episode=None;previous=999
for r in d['rows']:
 a=r['player']['attack']
 if not a:previous=999;continue
 if a[-1]<previous:
  episode={'delay':r['delay'],'hit':None,'samples':[]};episodes.append(episode)
 previous=a[-1]
 if a[3] and episode['hit'] is None:episode['hit']=a[-1]
 episode['samples'].append(r)
summary=[]
for e in episodes:
 if e['hit'] is None:continue
 deadline=e['hit']+e['delay'];after=[r for r in e['samples'] if r['player']['attack'][-1]>=e['hit']]
 for r in after:
  f=r['player']['attack'][-1];active='DODGING' in r['opponent']['activity']
  assert active==(f<deadline),(e['delay'],e['hit'],f,active,r['opponent'])
 expiry=next(r for r in after if r['player']['attack'][-1]>=deadline)
 assert expiry['player']['attack'][-1]==deadline
 summary.append(dict(delay=e['delay'],hit_frame=e['hit'],locomotion_frame=deadline,steps=expiry['opponent']['defense']['steps']))
assert {e['delay'] for e in summary}=={0,1,3}
result=dict(samples=len(d['rows']),episodes=summary)
(p.parent/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
