import json,math
from pathlib import Path
d=Path(__file__).parent
def lengths(r,kind='nn'):
 return [math.dist(r['bones']['hand_'+s][kind][:3],r['bones']['lowerarm_'+s][kind][:3]) for s in ('l','r')]
summary={}
for name in ('physical','kinematic','half','long','zero'):
 p=d/(name+'.json')
 if not p.exists():continue
 data=json.loads(p.read_text());rows=data['rows'];assert data['reason']=='Complete',data['reason']
 rest=lengths(rows[0]);episodes=[]
 for i,r in enumerate(rows):
  if i and not r['attack'] and rows[i-1]['attack']:
   # End captures the presented pose from the preceding tick. In the long/zero
   # case the diagnostic stop happens after capture of that tick's row.
   ticks=36 if name=='long' else 0 if name=='zero' else 18
   source=lengths(rows[i-1]);at_end=lengths(r)
   manual=name in ('long','zero') and len(episodes)==0
   origin=next(c['stop_tick'] for c in data['checks'] if 'stop_tick' in c) if manual else r['tick']
   seed=source if manual else at_end
   episode=[]
   for x in rows[i:]:
    if x['attack']:break
    t=x['tick']-origin;expected=[b+(a-b)*max(0,1-t/ticks) if ticks else b for a,b in zip(seed,rest)]
    actual=lengths(x)
    episode.append(dict(tick=x['tick'],error=max(abs(a-b) for a,b in zip(actual,expected)),nn=actual,physical=lengths(x,'body')))
   episodes.append(dict(start=r['tick'],return_ticks=ticks,capture_error=max(abs(a-b) for a,b in zip(source,at_end)),max_curve_error=max(x['error'] for x in episode),end=episode[-1]))
 summary[name]=dict(checks=data['checks'],modes=sorted(set(r['mode'] for r in rows)),episodes=episodes)
(d/'summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
