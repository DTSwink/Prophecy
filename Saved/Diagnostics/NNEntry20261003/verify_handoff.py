import json,sys,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
p=Path(__file__).resolve().parent
def rows(n):return {r['tick']:r for r in json.loads((p/(n+'.json')).read_text())['rows']}
mode=sys.argv[1] if len(sys.argv)>1 else 'after'
a=rows('before');b=rows(mode)
layout=json.loads((p.parents[2]/'Content/locomotion/NN/prophecy_upper_body_runtime.json').read_text())
def local(rs,t,n,k,parent):
    x=rs[t]['bones'][n][k];y=rs[t]['bones'][parent][k];q=R.from_quat(y['q'])
    return q.inv().apply(np.array(x['p'])-y['p']),q.inv()*R.from_quat(x['q'])
starts=[t for t in sorted(b) if t-1 in b and b[t-1]['attack']=='None' and b[t]['attack']!='None']
out={}
for entry in starts:
    first=next(t for t in range(entry+1,entry+4) if ', 2)' in b[t]['attack'])
    err={}
    for n in b[entry]['bones']:
        if n=='pelvis':continue
        parent=layout['body_names'][layout['parents_body'][layout['body_names'].index(n)]]
        if parent not in b[entry]['bones']:continue
        x,r=local(b,entry,n,'future',parent);y,s=local(b,first,n,'presented',parent)
        err[n]={'cm':float(np.linalg.norm(x-y)),'degrees':float(np.degrees((r.inv()*s).magnitude()))}
    out[str(entry)]={'first_prediction_tick':first,'outgoing_NN_endpoint_error':err}
before=[json.loads(t) for t in (p/'before-nn.jsonl').read_text().splitlines()]
after=[json.loads(t) for t in (p/(mode+'-nn.jsonl')).read_text().splitlines()]
x=next(t for t in before if t['actor'].endswith('_0') and t['frame']==2)
y=next(t for t in after if t['actor'].endswith('_0') and t['frame']==2)
out['first_NN_input_max_error']=max(abs(x-y) for x,y in zip(x['input'],y['input']))
out['first_NN_output_max_error']=max(abs(x-y) for x,y in zip(x['output'],y['output']))
for case in out.values():
    if isinstance(case,dict):
        assert all(e['cm']<1e-6 and e['degrees']<1e-6 for e in case['outgoing_NN_endpoint_error'].values())
if mode=='after':assert out['first_NN_input_max_error']==out['first_NN_output_max_error']==0
(p/(mode+'-handoff-verification.json')).write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
