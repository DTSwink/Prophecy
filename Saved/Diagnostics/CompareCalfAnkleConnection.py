import json,pathlib,math,contextlib,io
with contextlib.redirect_stdout(io.StringIO()):
    from AnalyzeCalfAnkleConnection import measure
p=pathlib.Path(__file__).parent
result={}
for tag in ('before','after'):
    d=json.loads((p/('CalfAnkleConnection-'+tag+'.json')).read_text())
    rows=[r for r in d['rows'] if r['actor']=='BP_ProphecyManualPoseAgent_C_1']
    exits=[i for i in range(1,len(rows)-60) if 'kick' in rows[i-1]['attack'] and 'kick' not in rows[i]['attack']]
    cases=[]
    for i in exits:
        case={'t':rows[i]['t'],'legs':{}}
        for s in ('l','r'):
            vals=[measure(r['meshes']['PhysicalMesh'],s) for r in rows[i:i+61]]
            case['legs'][s]={'first_three':vals[:3],'middle':vals[30],'last':vals[60],
                'entry_gap_step':vals[1]['tip_gap']-vals[0]['tip_gap'],
                'entry_scale_step':max(abs(a-b) for a,b in zip(vals[1]['scale'],vals[0]['scale'])),
                'max_gap_step':max(abs(a['tip_gap']-b['tip_gap']) for a,b in zip(vals,vals[1:])),
                'max_scale_change_during_return':max(abs(a-b) for v in vals[:60] for a,b in zip(v['scale'],vals[0]['scale']))}
        cases.append(case)
    result[tag]={'reason':d['reason'],'exits':len(exits),'cases':cases}
    print(tag,'complete exits',len(exits))
    for s in ('l','r'):
        print(s,{k:max(abs(c['legs'][s][k]) for c in cases) for k in ('entry_gap_step','entry_scale_step','max_gap_step','max_scale_change_during_return')})
if result['after']['exits']<4:raise AssertionError('Too few complete exits')
for c in result['after']['cases']:
    for s in ('l','r'):
        v=c['legs'][s]
        assert v['entry_scale_step']<1.e-4,v
        assert abs(v['entry_gap_step'])<.02,v
        assert v['max_scale_change_during_return']<1.e-4,v
        assert v['last']['tip_gap']<.02,v
(p/'CalfAnkleConnection-comparison.json').write_text(json.dumps(result,indent=2))
print('Mesh scale remains continuous and visible calf tip converges to ankle during recovery.')
