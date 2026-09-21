import json, pathlib, sys, numpy as np
root=pathlib.Path(sys.argv[1])
rows=[json.loads(x) for x in (root/'metrics.jsonl').read_text().splitlines()]
for name in sorted({r['agent'] for r in rows}):
    if not name.endswith('_C_1'):continue
    rs=[r for r in rows if r['agent']==name]
    print('\nAGENT',name,'rows',len(rs),'modes',set(r['mode'] for r in rs))
    print('tick attack alpha targetXYZ bodyXYZ dTarget dBody dRoot error')
    prev=None
    for r in rs:
        if prev and r['tick'] is not None and 155<=r['tick']<=195:
            p=r['bones']['pelvis'];q=prev['bones']['pelvis']
            t=np.array(p['target']['p']);b=np.array(p.get('body',p['visible'])['p'])
            td=t-q['target']['p'];bd=b-q.get('body',q['visible'])['p'];ad=np.array(r['actor']['p'])-prev['actor']['p']
            print(r['tick'],str(r['attack']),round(r['alpha'],3),np.round(t,2),np.round(b,2),np.round(td,3),np.round(bd,3),np.round(ad,3),round(np.linalg.norm(b-t),3))
        prev=r
