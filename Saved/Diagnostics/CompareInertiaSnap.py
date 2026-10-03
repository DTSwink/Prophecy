import json,pathlib,numpy as np
root=pathlib.Path('Saved/Diagnostics')
def load(name):
 p=root/name
 print(name,json.loads((p/'summary.json').read_text()))
 return [json.loads(x) for x in (p/'metrics.jsonl').read_text().splitlines() if json.loads(x)['agent'].endswith('_C_1')]
a=load('InertiaSnap-20260927-163350')
b=load('InertiaSnap-20260927-163609')
def pos(r,kind):return np.array(r['bones']['pelvis'][kind]['p'])
print('prefix target max delta',max(np.linalg.norm(pos(x,'target')-pos(y,'target')) for x,y in zip(a,b) if x['tick']<169))
for name,rows in [('before',a),('after',b)]:
 print(name,'transitions',[(r['tick'],r['attack']) for i,r in enumerate(rows) if i==0 or (str(r['attack'])[:27]!=str(rows[i-1]['attack'])[:27])])
 for lo,hi in [(165,172),(184,192),(455,468)]:
  for i,r in enumerate(rows):
   if i and lo<=r['tick']<=hi:
    d=pos(r,'target')-pos(rows[i-1],'target');physical=pos(r,'body')-pos(rows[i-1],'body')
    print(r['tick'],'targetDelta',np.round(d,3).tolist(),'len',round(np.linalg.norm(d),3),'bodyDelta',round(np.linalg.norm(physical),3),'targetFutureError',round(np.linalg.norm(pos(r,'target')-pos(r,'future')),4),'alpha',r['alpha'])
 print('max target step',max((np.linalg.norm(pos(r,'target')-pos(rows[i-1],'target')),r['tick']) for i,r in enumerate(rows) if i))
