import json,pathlib,math
p=pathlib.Path(__file__).parent
def mul(a,b):
 x,y,z,w=a;X,Y,Z,W=b
 return [w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z]
def rel(v,q):return mul(mul([-q[0],-q[1],-q[2],q[3]],v+[0]),q)[:3]
def dist(a,b):return math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))
def read(tag):
 d=json.loads((p/(tag+'.json')).read_text());assert not d['error'],d['error']
 rows=[r for r in d['rows'] if r['player']]
 for r in rows:
  bones=r['future'];spine=bones['spine_05'];r['local']={b:rel([a-c for a,c in zip(bones[b]['p'],spine['p'])],spine['q']) for b in ['hand_l','hand_r','lowerarm_l','lowerarm_r']}
 return {r['tick']:r for r in rows}
allrows={t:read(t) for t in ['baseline','no_cone_recovery'] if (p/(t+'.json')).exists()}
for tag,rows in allrows.items():
 steps=[]
 for t,r in rows.items():
  if t-2 in rows and 190<=t<=285:
   step={b:dist(r['local'][b],rows[t-2]['local'][b]) for b in ['hand_l','hand_r']}
   steps.append(dict(tick=t,**step,total=sum(step.values())))
 print(tag,'largest two-tick torso-local hand steps',sorted(steps,key=lambda r:r['total'],reverse=True)[:6])
 print('samples',[(t,[round(v,2) for v in rows[t]['local']['hand_l']],[round(v,2) for v in rows[t]['local']['hand_r']]) for t in [183,200,220,240,250,258,260,262,264,280]])
if len(allrows)==2:
 a,b=allrows.values(); print('pre-exit max difference',max(dist(a[t]['future']['hand_l']['p'],b[t]['future']['hand_l']['p']) for t in a if t<=183));print('post cone differences',[(t,round(dist(a[t]['local']['hand_l'],b[t]['local']['hand_l']),3),round(dist(a[t]['local']['hand_r'],b[t]['local']['hand_r']),3)) for t in [200,220,240,250,260,280]])
for tag,rows in allrows.items():
 print(tag,'hand forward distance from pelvis along travel')
 for t in [200,220,230,240,250,260,280]:
  root=rows[t]['future']['pelvis']['p'];old=rows[t-10]['future']['pelvis']['p']
  v=[root[0]-old[0],root[1]-old[1],0];length=math.sqrt(sum(x*x for x in v));v=[x/length for x in v]
  print(t,*(round(sum((rows[t]['future'][h]['p'][i]-root[i])*v[i] for i in range(3)),2) for h in ['hand_l','hand_r']))
