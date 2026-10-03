import json,sys,math
from pathlib import Path
p=Path(__file__).resolve().parent
mode=sys.argv[1] if len(sys.argv)>1 else 'baseline'
d=json.loads((p/(mode+'.json')).read_text(encoding='utf8'))
print('capture',d['reason'],'owned',d['owned'],'rows',len(d['rows']))
last=None
for i,r in enumerate(d['rows']):
 if r['attack']!=last and (last is None or 'policy_frame=0' in r['attack'] or 'policy_frame=1)' in r['attack']):print(r['tick'],r['attack'],r['drag'])
 last=r['attack']
for r in d['rows']:
 if 162<=r['tick']<=192:
  b=r['bones']['pelvis']
  print(r['tick'],r['attack'],'drag',r['drag'],'root',*[round(x,2) for x in r['root']], 'future',*[round(x,2) for x in b['future']['p']],'presented',*[round(x,2) for x in b['presented']['p']],'target',*[round(x,2) for x in b['target']['p']],'body',*[round(x,2) for x in b['body']['p']])
