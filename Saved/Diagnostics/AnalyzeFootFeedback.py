import json,pathlib,math
root=pathlib.Path('Saved/Diagnostics')
def load(p):
 assert json.loads((p/'summary.json').read_text())['error'] is None
 return [json.loads(l) for l in (p/'metrics.jsonl').read_text().splitlines() if json.loads(l)['agent']=='BP_ProphecyManualPoseAgent_C_1']
before=load(root/'FootHandoffSnap-20260927-184704')
path=sorted(root.glob('FootHandoffSnap-*'))[-1];after=load(path)
for title,rr in [('before',before),('after',after)]:
 print(title)
 for i,r in enumerate(rr):
  if i and (r['owners']!=rr[i-1]['owners'] or bool(r['attack'])!=bool(rr[i-1]['attack'])):
   print('event',r['tick'],r['owners'],r['attack'])
   if r['tick']>300 and r['attack']:
    for side,bone in enumerate(('foot_l','foot_r')):
     if rr[i-1]['owners'][side] and not r['owners'][side]:
      print('release',bone,'steps',[round(math.dist(b['bones'][bone]['drive']['p'],a['bones'][bone]['drive']['p']),3) for a,b in zip(rr[i-1:i+7],rr[i:i+8])])
 group=[r for r in rr if r['tick'] and 350<=r['tick']<=369]
 for bone in ('foot_l','foot_r'):
  print('350-369 max',bone,max(math.dist(a['bones'][bone]['drive']['p'],b['bones'][bone]['drive']['p']) for a,b in zip(group,group[1:])))
print('capture',path)
