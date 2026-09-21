import json, math, pathlib, sys
p=pathlib.Path(sys.argv[1])
rows=[json.loads(l) for l in (p/'metrics.jsonl').open()]
def sub(a,b): return [x-y for x,y in zip(a,b)]
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def norm(a): return math.sqrt(dot(a,a))
def angle(a,b): return math.degrees(math.acos(max(-1,min(1,dot(a,b)/max(1e-12,norm(a)*norm(b))))))
def metric(m):
    h,k,a,t=m['points']; u=sub(k,h); f=sub(t,a); fl=math.hypot(*f[:2])
    if fl<3 or math.hypot(*u[:2])<5:return None
    f=[f[0]/fl,f[1]/fl,0]; right=[-f[1],f[0],0]
    local=[dot(u,f),dot(u,right),u[2]]
    return dict(yaw=math.degrees(math.atan2(local[1],local[0])),forward_cm=local[0],side_cm=local[1],local=local)
for agent in sorted(set(r['agent'] for r in rows)):
    seq=[r for r in rows if r['agent']==agent and r['side']=='l']; out=[]; previous=None
    for r in seq:
        d={s:metric(m) for s,m in r['metrics'].items()}; d={s:v for s,v in d.items() if v}
        row=dict(frame=r['frame'],time=r['time'],attack=r['attack'],sources=d)
        if previous and r['frame']==previous['frame']+1:
            for s,m in d.items():
                old=previous['sources'].get(s)
                if old:
                    m['step_deg']=angle(m['local'],old['local'])
                    m['yaw_step']=(m['yaw']-old['yaw']+180)%360-180
        out.append(row); previous=row
    print('\nAGENT',agent)
    def short(r):
        return {'frame':r['frame'],'attack':r['attack'],'sources':{s:{k:round(v,2) for k,v in m.items() if k!='local'} for s,m in r['sources'].items()}}
    recovery=[r for r in out if not r['attack'] and r['frame']>60 and 'physical' in r['sources']]
    sideways=sorted(recovery,key=lambda r:abs(abs(r['sources']['physical']['yaw'])-90))[:3]
    print('SIDEWAYS',json.dumps([short(r) for r in sideways]))
    jumps=sorted([r for r in recovery if r['frame']>1 and 'step_deg' in r['sources']['physical'] and not seq[r['frame']-2]['attack']],key=lambda r:r['sources']['physical']['step_deg'],reverse=True)[:3]
    print('RECOVERY_STEPS',json.dumps([short(r) for r in jumps]))
    reversals=[]
    for a,b in zip(out,out[1:]):
        if a['attack'] or b['attack'] or a['frame']<60:continue
        aa=a['sources'].get('physical',{}).get('yaw_step',0); bb=b['sources'].get('physical',{}).get('yaw_step',0)
        if aa*bb<0 and min(abs(aa),abs(bb))>2:reversals.append((min(abs(aa),abs(bb)),a,b))
    reversals.sort(key=lambda x:x[0],reverse=True)
    print('REVERSALS',len(reversals),json.dumps([[short(a),short(b)] for _,a,b in reversals[:2]]))
    (p/(agent+'-thigh-analysis.json')).write_text(json.dumps(out))
