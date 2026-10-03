from pathlib import Path
exec(Path('Saved/Diagnostics/AnalyzePikeReturn.py').read_text().split("a,b=load('legacy')")[0])
import sys
p=Path('Saved/Diagnostics/ArmReach');tags=sys.argv[1:] or ['variants']
first=None
for tag in tags:
 data=json.loads((p/(tag+'.json')).read_text());assert data['reason']=='Complete'
 d={r['frame']:r for r in data['rows']}
 if first is None:first=d
 print(tag,'prefix',max(np.linalg.norm(np.array(v['future']['p'])-first[t]['pose'][n]['future']['p']) for t in d if t<=487 for n,v in d[t]['pose'].items()))
 scores=[]
 for t in range(488,540):
  h,q,w=local(d[t],'presented');base,tip,pad=geometry(d[t]);score=clearance(h,q,w,base,tip,pad)
  scores.append((score,t))
 print('WORST',sorted(scores)[:8])
 for t in [488,490,494,500,510,520,530,539]:
  h,q,w=local(d[t],'future');base,tip,pad=geometry(d[t]);score=clearance(h,q,w,base,tip,pad)
  b={n:v['future'] for n,v in d[t]['pose'].items()};o,rot,_=torso(b)
  s=rot.inv().apply(np.array(b['upperarm_r']['p'])-o);e=rot.inv().apply(np.array(b['lowerarm_r']['p'])-o)
  print(t,'future blade clearance',round(score,4),'hand',h.round(1),'upper',round(np.linalg.norm(e-s),2),'lower',round(np.linalg.norm(h-e),2))
