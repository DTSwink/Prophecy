import json,pathlib,math
root=pathlib.Path(__file__).parent
def dist(r,s,k):
    return math.dist(r['bones']['calf_'+s][k]['p'],r['bones']['foot_'+s][k]['p'])
def angle(a,b):
    return math.degrees(2*math.acos(min(1,abs(sum(x*y for x,y in zip(a,b))))))
summary={}
for name,file in [('before','KickFootSnap.json'),('after','KickFootSnap-fixed.json')]:
    data=json.loads((root/file).read_text());allrows=data['rows']
    agent=next(r['actor'] for r in allrows if 'kick' in r['attack'])
    rows=[r for r in allrows if r['actor']==agent]
    exits=[i for i in range(1,len(rows)) if 'kick' in rows[i-1]['attack'] and 'kick' not in rows[i]['attack']]
    captures=[]
    for i in exits:
        window=rows[i-1:i+61]
        item={'time':rows[i]['t'],'feet':{}}
        for s in ('l','r'):
            d={k:[dist(r,s,k) for r in window] for k in ('physical','target','future')}
            entry={'first_5':{k:[round(v,4) for v in vs[:5]] for k,vs in d.items()},
                'first_2_tick_contraction':d['physical'][0]-d['physical'][2],
                'largest_target_length_step':max(abs(b-a) for a,b in zip(d['target'],d['target'][1:])),
                'largest_physical_length_step':max(abs(b-a) for a,b in zip(d['physical'],d['physical'][1:])),
                'length_at_60':d['target'][-1],
                'calf_target_rotation_step':max(angle(a['bones']['calf_'+s]['target']['q'],b['bones']['calf_'+s]['target']['q']) for a,b in zip(window,window[1:]))}
            if 'thigh_'+s in window[0]['bones']:
                entry['thigh_target_rotation_step']=max(angle(a['bones']['thigh_'+s]['target']['q'],b['bones']['thigh_'+s]['target']['q']) for a,b in zip(window,window[1:]))
            item['feet'][s]=entry
        captures.append(item)
        if name=='after' and len(window)>=61:
            for side in ('l','r'):
                nominal=42.5633 if side=='l' else 42.5635
                initial=dist(window[1],side,'target')-nominal
                errors=[]
                for j,r in enumerate(window[1:61]):
                    alpha=j/60
                    expected=nominal+initial*(1-alpha*alpha*(3-2*alpha))
                    errors.append(abs(dist(r,side,'target')-expected))
                item['feet'][side]['return_curve_error_cm']=max(errors)
                assert max(errors)<.002,(side,i,max(errors))
    summary[name]={'reason':data['reason'],'exits':captures}
    print(name,'exits',len(exits))
    for e in captures[:3]:print(json.dumps(e))
    for s in ('l','r'):
        print(s,'max 2tick contraction',max(e['feet'][s]['first_2_tick_contraction'] for e in captures),
            'max target step',max(e['feet'][s]['largest_target_length_step'] for e in captures),
            'max calf angle step',max(e['feet'][s]['calf_target_rotation_step'] for e in captures))
(root/'KickFootSnap-comparison.json').write_text(json.dumps(summary,indent=2))
