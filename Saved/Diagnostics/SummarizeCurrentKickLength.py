import json, math, pathlib
p=pathlib.Path(__file__).parent
summary={}
for tag in ('currentRotation','currentRotation-no_reconstruction','currentRotation-profile'):
    f=p/('KickFootSnap-'+tag+'.json')
    if not f.exists(): continue
    data=json.loads(f.read_text())
    rows=[r for r in data['rows'] if r['actor']=='BP_ProphecyManualPoseAgent_C_1']
    exits=[i for i in range(1,len(rows)) if 'kick' in rows[i-1]['attack'] and 'kick' not in rows[i]['attack']]
    def length(r,s,k):return round(math.dist(r['bones']['calf_'+s][k]['p'],r['bones']['foot_'+s][k]['p']),5)
    captures=[]
    for i in exits[:4]:
        window=rows[i:i+61]
        captures.append({'time':rows[i]['t'],'first_three_lengths':{s:{k:[length(r,s,k) for r in window[:3]] for k in ('target','future','physical')} for s in ('l','r')},
            'clamp_prints':[{ 'tick':j,'foot_rows':[line for line in r.get('profile','').splitlines() if line.startswith('foot_')]} for j,r in enumerate(window) if j in (0,1,2,15,30,59,60)]})
    summary[tag]={'reason':data['reason'],'samples':len(rows),'exits':len(exits),'captures':captures}
    print(tag, 'exits',len(exits))
    if captures: print(json.dumps(captures[min(1,len(captures)-1)],indent=2))
(p/'CurrentKickLengthDiagnosis.json').write_text(json.dumps(summary,indent=2))
