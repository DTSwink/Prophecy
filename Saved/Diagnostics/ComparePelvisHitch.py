import json,pathlib,numpy as np
root=pathlib.Path(__file__).parent
paths=sorted(root.glob('PelvisHitch-*/summary.json'))
base=None;bp=None
for path in paths:
    p=path.parent
    rows=[json.loads(x) for x in (p/'metrics.jsonl').read_text().splitlines()]
    rs={r['tick']:r for r in rows if r['agent'].endswith('_C_1')}
    ps=[json.loads(x) for x in (p/'pipeline.jsonl').read_text().splitlines()]
    ps={round(r['time']*60):r for r in ps if r['actor'].endswith('_C_1')}
    if base is None:base=rs;bp=ps
    pre=max(np.linalg.norm(np.array(r['bones']['pelvis']['target']['p'])-base[t]['bones']['pelvis']['target']['p']) for t,r in rs.items() if t<=148 and t in base)
    rootdiff=max(np.linalg.norm(np.array(r['actor']['p'])-base[t]['actor']['p']) for t,r in rs.items() if 149<=t<=190 and t in base)
    print('\n',p.name, (p/'variant.txt').read_text() if (p/'variant.txt').exists() else '', 'pre148max',pre,'root149190max',rootdiff)
    print('Y distance / frame:',[(t,round(rs[t-1]['bones']['pelvis']['target']['p'][1]-rs[t]['bones']['pelvis']['target']['p'][1],3)) for t in range(171,185,2) if t in rs])
    print('raw output pelvis XYZ:',[(t,np.round(ps[t]['lower_delta'][:3],4).tolist()) for t in range(171,183,2) if t in ps])
    residual=[]
    for t,r in ps.items():
        if not 151<=t<=195:continue
        current=np.array(r['lower_input'][:3]);raw=current+np.array(r['lower_delta'][:3]);previous=np.array(r['previous_lower'][:3])
        temp=r.get('tempering',[1]*6);strength=np.array([temp[2],temp[2],temp[5]])
        expected=previous+(raw-previous)*strength
        residual.append(np.linalg.norm(expected-r['published_lower'][:3])*100)
    print('max pelvis correction residual cm',max(residual))
