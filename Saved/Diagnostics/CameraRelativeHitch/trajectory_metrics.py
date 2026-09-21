import collections, json, math, pathlib, statistics, sys

root = pathlib.Path(__file__).resolve().parent
def norm(v): return math.sqrt(sum(x*x for x in v))
def sub(a,b): return [x-y for x,y in zip(a,b)]
def summary(values):
    values=sorted(values)
    return dict(n=len(values), mean=statistics.mean(values), min=values[0],
                p99=values[int((len(values)-1)*.99)], max=values[-1]) if values else None

results=[]
for arg in sys.argv[1:]:
    path=root/arg
    data=json.loads(path.read_text()); rows=data['rows']
    groups=collections.defaultdict(list); events=[]
    for a,b in zip(rows,rows[1:]):
        if b['t'] < rows[0]['t']+5 or norm(b['mover_v'])<20 or norm(sub(a['mover_v'],b['mover_v']))>.1: continue
        dt=b['t']-a['t']; speed=norm(b['mover_v']); direction=[v/speed for v in b['mover_v']]
        dot=lambda v:sum(x*y for x,y in zip(v,direction))
        step_max=data['metadata']['physics']['max_substep_delta_time']
        steps=max(1,math.ceil(b['dt']/step_max))
        err=sub(b['pelvis'],b['target']); olderr=sub(a['pelvis'],a['target'])
        event=dict(t=b['t'],dt=b['dt'],alpha=b['alpha'],steps=steps,
            native_forward_speed=dot(b['body_v']),root_forward_speed=dot(sub(b['root'],a['root']))/dt,
            target_forward_speed=dot(sub(b['target'],a['target']))/dt,
            visible_forward_speed=dot(sub(b['visible'],a['visible']))/dt,
            position_tracking_jump=norm(sub(err,olderr)),
            target_relative_jump=norm(sub(sub(b['target'],b['root']),sub(a['target'],a['root']))),
            visible_relative_jump=norm(sub(sub(b['visible'],b['root']),sub(a['visible'],a['root']))))
        groups[steps].append(event); events.append(event)
    result=dict(source=path.name,rows=len(rows),duration=rows[-1]['t']-rows[0]['t'],
        metadata=data['metadata'],final_settings=data.get('final_settings'),
        groups={n:{key:summary([e[key] for e in es]) for key in es[0] if key not in ('t','steps','alpha')}
                for n,es in groups.items()},
        top_tracking_jumps=sorted(events,key=lambda e:e['position_tracking_jump'],reverse=True)[:10],
        top_target_jumps=sorted(events,key=lambda e:e['target_relative_jump'],reverse=True)[:10],
        top_visible_jumps=sorted(events,key=lambda e:e['visible_relative_jump'],reverse=True)[:10])
    (root/(path.stem+'-trajectory-metrics.json')).write_text(json.dumps(result,indent=2))
    results.append(result)
print(json.dumps(results,indent=2))
