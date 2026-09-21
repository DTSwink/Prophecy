import pathlib,json,sys,math
def sub(a,b):return [x-y for x,y in zip(a,b)]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def length(a):return math.sqrt(dot(a,a))
def q95(v):return sorted(v)[int(.95*(len(v)-1))] if v else None
p=pathlib.Path(sys.argv[1]); buckets={}; prior={}; kicks={}
for line in (p/'metrics.jsonl').open():
    r=json.loads(line)
    if r['side']!='l':continue
    actor=r['agent'];attack=bool(r['attack'])
    if attack and not prior.get(actor,False):kicks[actor]=kicks.get(actor,0)+1
    prior[actor]=attack; kick=kicks.get(actor,0)
    if attack or kick==0:continue
    for source,pose in r['poses'].items():
        h,k,a,t=pose['points'];u=sub(k,h);f=sub(t,a);fl=math.hypot(f[0],f[1])
        if fl<3 or length(u)<1:continue
        side=[-f[1]/fl,f[0]/fl,0];lateral=dot(u,side)
        entry=dict(frame=r['frame'],time=r['time'],side_cm=lateral,
            abduction=math.degrees(math.asin(min(1,abs(lateral)/length(u)))),
            ankle_side_cm=dot(sub(a,h),side),mode=r['mode'])
        buckets.setdefault((actor,kick,source),[]).append(entry)
out=[]
for (actor,kick,source),rs in buckets.items():
    out.append(dict(actor=actor,kick=kick,source=source,samples=len(rs),
        abduction_p95=q95([r['abduction'] for r in rs]),
        lateral_p95_cm=q95([abs(r['side_cm']) for r in rs]),
        worst=max(rs,key=lambda r:r['abduction'])))
(p/'outward-by-kick.json').write_text(json.dumps(out,indent=2))
for r in out:
    if r['actor']=='BP_ProphecyManualPoseAgent_C_1' and r['source'] in ('future','presented'):
        print(json.dumps(r))
