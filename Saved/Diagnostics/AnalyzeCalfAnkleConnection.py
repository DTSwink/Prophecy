import json,pathlib,math,sys
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def norm(a):return math.sqrt(dot(a,a))
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def rotate(q,v):
    c=cross(q[:3],v);cc=cross(q[:3],c)
    return [v[i]+2*(q[3]*c[i]+cc[i]) for i in range(3)]
p=pathlib.Path(__file__).parent
tag=sys.argv[1] if len(sys.argv)>1 else 'before'
d=json.loads((p/('CalfAnkleConnection-'+tag+'.json')).read_text())
r=[x for x in d['rows'] if x['actor']=='BP_ProphecyManualPoseAgent_C_1']
ex=[i for i in range(1,len(r)) if 'kick' in r[i-1]['attack'] and 'kick' not in r[i]['attack']]
def measure(b,s):
    c,f=b['calf_'+s],b['foot_'+s]
    off=[-42.561031,.107739,.42919] if s=='l' else [42.561165,-.107729,-.429205]
    ray=rotate(c['q'],[off[i]*c['s'][i] for i in range(3)])
    delta=[f['p'][i]-c['p'][i] for i in range(3)]
    return {'length':norm(delta),'scale':c['s'],'tip_gap':norm([delta[i]-ray[i] for i in range(3)]),
        'axis_error_deg':math.degrees(math.acos(max(-1,min(1,dot(ray,delta)/(norm(ray)*norm(delta))))))}
summary=[]
for i in ex:
    out={'t':r[i]['t'],'frames':[]}
    for j in (-2,-1,0,1,2,3,30,59,60,61):
        if i+j>=len(r):continue
        x=r[i+j]
        out['frames'].append({'tick':j,'meshes':{m:{s:measure(b,s) for s in ('l','r')} for m,b in x['meshes'].items() if 'calf_l' in b}})
    summary.append(out)
(p/('CalfAnkleConnection-'+tag+'-summary.json')).write_text(json.dumps(summary,indent=2))
print('reason',d['reason'],'exits',len(ex),'meshes',list(r[0]['meshes']) if r else [])
for x in summary[:2]:print(json.dumps(x))
