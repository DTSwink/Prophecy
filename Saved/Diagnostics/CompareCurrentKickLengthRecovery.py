import json,math,pathlib
p=pathlib.Path(__file__).parent
result={}
def length(r,s,kind='target'):return math.dist(r['bones']['calf_'+s][kind]['p'],r['bones']['foot_'+s][kind]['p'])
def angle(a,b):return math.degrees(2*math.acos(min(1,abs(sum(x*y for x,y in zip(a,b))))))
for tag in ('currentRotation','currentRotation-verified'):
    data=json.loads((p/('KickFootSnap-'+tag+'.json')).read_text())
    rows=[r for r in data['rows'] if r['actor']=='BP_ProphecyManualPoseAgent_C_1']
    exits=[i for i in range(1,len(rows)) if 'kick' in rows[i-1]['attack'] and 'kick' not in rows[i]['attack']]
    items=[]
    for i in exits:
        w=rows[i:i+61]
        if len(w)<61:continue
        item={'t':rows[i]['t'],'legs':{}}
        for s in ('l','r'):
            ls=[length(r,s) for r in w]
            rest=42.56334 if s=='l' else 42.56333
            error=max(abs(x-(rest+(ls[0]-rest)*(1-(j/60)**2*(3-2*j/60)))) for j,x in enumerate(ls))
            item['legs'][s]={'first3':ls[:3],'two_tick_change':ls[2]-ls[0],'max_length_step':max(abs(a-b) for a,b in zip(ls,ls[1:])),
                'curve_error_cm':error,'angle_step':{b:max(angle(a['bones'][b+'_'+s]['target']['q'],c['bones'][b+'_'+s]['target']['q']) for a,c in zip(w,w[1:])) for b in ('thigh','calf','foot')}}
            physical=[length(r,s,'physical') for r in w]
            item['legs'][s]['physical_two_tick_change']=physical[2]-physical[0]
            item['legs'][s]['physical_curve_error_cm']=max(abs(x-(rest+(physical[0]-rest)*(1-(j/60)**2*(3-2*j/60)))) for j,x in enumerate(physical))
            item['legs'][s]['target_physical_length_difference']=max(abs(a-b) for a,b in zip(ls,physical))
        items.append(item)
    result[tag]={'reason':data['reason'],'exits':len(exits),'windows':items}
    print(tag, 'exits',len(exits))
    for s in ('l','r'):
        print(s,{k:max(abs(x['legs'][s][k]) for x in items) for k in ('two_tick_change','max_length_step','curve_error_cm')})
    if items:print('second exit',json.dumps(items[min(1,len(items)-1)]))
(p/'CurrentKickLengthRecoveryComparison.json').write_text(json.dumps(result,indent=2))
for x in result['currentRotation-verified']['windows']:
    for s in ('l','r'):
        v=x['legs'][s]
        assert v['curve_error_cm']<.02,v
        assert v['physical_curve_error_cm']<.02,v
        assert v['target_physical_length_difference']<.02,v
print('All captured recovery windows follow the signed 60-tick curve and agree with kinematic physics within 0.02 cm.')
