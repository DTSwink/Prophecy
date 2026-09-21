import json,pathlib,sys,numpy as np
root=pathlib.Path(sys.argv[1]);rows=[json.loads(x) for x in (root/'pipeline.jsonl').read_text().splitlines()]
rs=[r for r in rows if r['actor'].endswith('_C_1')]
print('pipeline',len(rs),'keys',rs[0].keys())
for i,r in enumerate(rs):
    tick=round(r['time']*60)
    if 110<=tick<=210:
        print(tick,'attack',r['attack'],'walk',round(r['walk_weight'],4),'temp',np.round(r.get('tempering',[]),4),
              'pub',np.round(r['published_lower'][:3],4),'prev',np.round(r['previous_lower'][:3],4),'delta',np.round(r['lower_delta'][:3],4),'roots',np.round(r['roots'][4:7],4))
print('Attack transitions',[(round(r['time']*60),r['attack']) for i,r in enumerate(rs) if i==0 or r['attack']!=rs[i-1]['attack']])
