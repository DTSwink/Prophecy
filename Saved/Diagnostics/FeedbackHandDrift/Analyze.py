import json,pathlib,math,statistics,sys
folder=pathlib.Path(__file__).parent
def length(v): return math.sqrt(sum(x*x for x in v))
def sub(a,b): return [x-y for x,y in zip(a,b)]
def angle(a,b): return math.degrees(2*math.acos(min(1,abs(sum(x*y for x,y in zip(a,b)))/(length(a)*length(b)))))
for mode in sys.argv[1:] or ['jolt','chaos']:
 p=folder/(mode+'.json')
 if not p.exists():continue
 d=json.loads(p.read_text()); print(mode,d['reason'],'samples',len(d['rows']))
 for actor in sorted(set(r['actor'] for r in d['rows'])):
  rows=[r for r in d['rows'] if r['actor']==actor and r['t']>5]
  print(actor)
  for bone in ('upperarm_l','upperarm_r','lowerarm_l','lowerarm_r','hand_l','hand_r'):
   b=[r['bones'][bone] for r in rows if bone in r['bones']]
   if not b:continue
   e=[length(sub(x['p'],x['target'])) for x in b]; q=[angle(x['q'],x['tq']) for x in b]
   w=[length(x['w']) for x in b]
   print(bone,'cm mean/max',round(statistics.mean(e),2),round(max(e),2),'deg mean/max',round(statistics.mean(q),2),round(max(q),2),'w max',round(max(w),2))
