import collections,json,math,pathlib,statistics,sys
path=pathlib.Path(sys.argv[1]); data=json.loads(path.read_text()); rows=data['rows']
def norm(v): return math.sqrt(sum(x*x for x in v))
def sub(a,b): return [x-y for x,y in zip(a,b)]
groups=collections.defaultdict(list)
for a,b in zip(rows,rows[1:]):
    if a['phase']!=b['phase'] or (b['t']-rows[0]['t'])%30<2: continue
    err=sub(b['bones']['pelvis']['visible'],b['bones']['pelvis']['target'])
    old=sub(a['bones']['pelvis']['visible'],a['bones']['pelvis']['target'])
    groups[b['phase']].append(dict(t=b['t'],dt=b['dt'],jolt=b['jolt'],mode=b['mode'],
        pelvis_tracking_delta=norm(sub(err,old)),
        pelvis_relative_delta=norm(sub(sub(b['bones']['pelvis']['visible'],b['root']),sub(a['bones']['pelvis']['visible'],a['root']))),
        target_relative_delta=norm(sub(sub(b['bones']['pelvis']['target'],b['root']),sub(a['bones']['pelvis']['target'],a['root']))),
        bone_tracking_deltas={bone:norm(sub(sub(b['bones'][bone]['visible'],b['bones'][bone]['target']),sub(a['bones'][bone]['visible'],a['bones'][bone]['target']))) for bone in b['bones']}))
result={'source':str(path),'error':data['error'],'events':data['events'],'phases':{}}
for key,events in groups.items():
    tracking=sorted(e['pelvis_tracking_delta'] for e in events)
    result['phases'][key]={'count':len(events),'modes':list({e['mode'] for e in events}),'backends':list({e['jolt'] for e in events}),
        'dt_range':[min(e['dt'] for e in events),max(e['dt'] for e in events)],
        'pelvis_tracking_delta_mean':statistics.mean(tracking),'pelvis_tracking_delta_p99':tracking[int(.99*(len(tracking)-1))],
        'top':sorted(events,key=lambda e:e['pelvis_tracking_delta'],reverse=True)[:4]}
path.with_name(path.stem+'-analysis.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
