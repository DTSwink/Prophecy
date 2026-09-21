import json,math,pathlib,sys
def sub(a,b):return [x-y for x,y in zip(a,b)]
def mul(a,k):return [x*k for x in a]
def add(a,b):return [x+y for x,y in zip(a,b)]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def norm(v):return math.sqrt(dot(v,v))
def unit(v):return mul(v,1/max(1e-12,norm(v)))
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def sample(r):
    m=r.get('poses',r['metrics']).get('future')
    if not m:return None
    h,k,a,t=m['points'];axis=unit(sub(a,h));up=sub(k,h);p=sub(up,mul(axis,dot(up,axis)))
    if norm(p)<3:return None
    return axis,unit(p)
for folder in sys.argv[1:]:
    p=pathlib.Path(folder);rs=[json.loads(l) for l in (p/'metrics.jsonl').open()]
    rs=[r for r in rs if r['agent']=='BP_ProphecyManualPoseAgent_C_1' and r['side']=='l'];prev=None;data=[]
    for r in rs:
        s=sample(r)
        if s and prev and not r['attack'] and not prev[0]['attack'] and r['frame']>60:
            a,old=prev[1];b,new=s;c=dot(a,b)
            if c>-.9999:
                carried=unit(sub(old,mul(add(a,b),dot(old,b)/(1+c))))
                angle=math.degrees(math.atan2(dot(b,cross(carried,new)),dot(carried,new)))
                if abs(angle)>1e-3:data.append({'frame':r['frame'],'angle':angle})
        prev=(r,s) if s else None
    vals=sorted(abs(r['angle']) for r in data)
    result={'capture':folder,'max_orbit_deg':max(vals,default=0),'p95_orbit_deg':vals[int(.95*(len(vals)-1))] if vals else 0,'worst':sorted(data,key=lambda r:abs(r['angle']),reverse=True)[:4]}
    print(json.dumps(result));(p/'orbit-summary.json').write_text(json.dumps(result,indent=2))
