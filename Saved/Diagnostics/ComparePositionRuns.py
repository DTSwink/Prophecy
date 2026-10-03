import json,pathlib,numpy as np
p=pathlib.Path('Saved/Diagnostics/PositionCompensation')
report={}
for mode in ['single','distributed']:
    a,b=[json.loads((p/(mode+'_'+tag+'.json')).read_text())['rows'] for tag in ['off','on']]
    ta,tb=[[json.loads(x) for x in (p/(mode+'_'+tag+'-trace.jsonl')).read_text().splitlines()] for tag in ['off','on']]
    half=lambda r:r['state'] and r['state'][1]
    pre=lambda rows:[r for r in rows if r['frame']<127]
    lower=['pelvis','thigh_l','calf_l','foot_l','ball_l','thigh_r','calf_r','foot_r','ball_r']
    d=dict(samples=[len(a),len(b)],pre_half_equal=pre(a)==pre(b),
        targets_equal=[r['targets'] for r in a]==[r['targets'] for r in b],
        ghost_equal=[(r['family'],r['frame'],r['input'],r['output'],r['anchor']) for r in ta]==[(r['family'],r['frame'],r['input'],r['output'],r['anchor']) for r in tb],
        half_lower_equal=all(all(x['future'][x['names'].index(n)]==y['future'][y['names'].index(n)] for n in lower) for x,y in zip(a,b) if half(x) and half(y)))
    changes=[]
    for x,y in zip(a,b):
        if not (half(x) and half(y)):continue
        deltas={n:float(np.linalg.norm(np.array(x['future'][x['names'].index(n)][:3])-y['future'][y['names'].index(n)][:3])) for n in lower}
        if max(deltas.values())>1.e-6:changes.append(dict(frame=x['frame'],max_cm=max(deltas.values()),pelvis_cm=deltas['pelvis']))
    d['first_lower_position_change']=changes[0] if changes else None
    d['max_lower_position_change_cm']=max([r['max_cm'] for r in changes],default=0)
    report[mode]=d
print(json.dumps(report,indent=2));(p/'parity.json').write_text(json.dumps(report,indent=2))
