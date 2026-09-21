import json, math, pathlib, sys
root = pathlib.Path(__file__).resolve().parent
path = pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else max(root.glob('capture-*.json'))
capture = json.loads(path.read_text())
rows = capture['rows']
events = []
steady = []
for i,(a,b) in enumerate(zip(rows, rows[1:]),1):
    if b['t'] < rows[0]['t']+5: continue
    speed = math.hypot(*b['mover_v'][:2])
    if speed < 20: continue
    dt = b['t']-a['t']
    direction = [v/speed for v in b['mover_v'][:2]]
    delta = {k: sum((b[k][j]-a[k][j])*direction[j] for j in range(2)) for k in ('capsule','target','future','body')}
    event = dict(i=i,t=b['t'],dt=dt,previous_dt=a['dt'],alpha_before=a['alpha'],alpha=b['alpha'],**delta)
    event['relative_body'] = delta['body']-delta['capsule']
    event['target_speed_ratio'] = delta['target']/(speed*dt)
    steady.append(event)
    if min(delta['body'],delta['target'],delta['capsule']) < -.01: events.append(event)
result = dict(source=str(path),metadata=capture['metadata'],reason=capture['reason'],error=capture['error'],rows=len(rows),
    event_count=len(events),events=sorted(events,key=lambda e:e['body'])[:20],
    extrema={k:[min(x[k] for x in steady),max(x[k] for x in steady)] for k in ('capsule','target','future','body','relative_body','target_speed_ratio')},
    worst_relative=sorted(steady,key=lambda x:x['relative_body'])[:10],
    near_stops=[x for x in steady if x['target_speed_ratio'] < .05][:20])
(root/(path.stem+'-analysis.json')).write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
if events:
    worst=min(events,key=lambda x:x['body'])['i']
    (root/'worst-event.json').write_text(json.dumps(rows[max(0,worst-6):worst+7],indent=2))
