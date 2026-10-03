import json,math,pathlib,sys
p=pathlib.Path(__file__).parent
tag=sys.argv[1] if len(sys.argv)>1 else 'knee-regression'
d=json.loads((p/('CalfAnkleConnection-'+tag+'.json')).read_text())
def sub(a,b):return [x-y for x,y in zip(a,b)]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def mul(a,s):return [x*s for x in a]
def norm(a):return math.sqrt(dot(a,a))
def unit(a):return mul(a,1/max(norm(a),1e-12))
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def qa(a,b):return math.degrees(2*math.acos(min(1,abs(dot(a,b)))))
def geom(b,s):
 h,k,f=[b[x+'_'+s]['p'] for x in ('thigh','calf','foot')]
 axis=unit(sub(f,h));u=sub(k,h);rad=sub(u,mul(axis,dot(u,axis)))
 return axis,unit(rad),norm(rad)
def step(a,b,s):
 ax,po,ra=geom(a,s);bx,bp,rb=geom(b,s)
 # Minimal-swing transport to distinguish knee swivel from endpoint motion.
 c=dot(ax,bx)
 carried=sub(po,mul([x+y for x,y in zip(ax,bx)],dot(po,bx)/max(1e-8,1+c)))
 angle=math.degrees(math.atan2(dot(bx,cross(carried,bp)),dot(carried,bp)))
 return dict(swivel=angle,radius0=ra,radius1=rb,thigh=qa(a['thigh_'+s]['q'],b['thigh_'+s]['q']),calf=qa(a['calf_'+s]['q'],b['calf_'+s]['q']))
out={}
for actor in sorted(set(r['actor'] for r in d['rows'])):
 rows=[r for r in d['rows'] if r['actor']==actor]
 if not any('kick' in r['attack'] for r in rows):continue
 results={}
 for path in ('PhysicalMesh','target','previous','future'):
  def bones(r):return r['meshes'][path] if path=='PhysicalMesh' else {b:t[path] for b,t in r['targets'].items()}
  steps=[]
  for i in range(1,len(rows)):
   for s in ('l','r'):
    q=step(bones(rows[i-1]),bones(rows[i]),s)
    q.update(t=rows[i]['t'],i=i,side=s,attack=rows[i]['attack'],before=rows[i-1]['attack'])
    steps.append(q)
  results[path]=dict(worst=sorted(steps,key=lambda x:x['thigh'],reverse=True)[:12],swivels=sorted(steps,key=lambda x:abs(x['swivel']),reverse=True)[:12])
  for s in ('l','r'):
   ss=[q for q in steps if q['side']==s]
   print(actor,path,s,'max thigh',max(x['thigh'] for x in ss),'max swivel',max(abs(x['swivel']) for x in ss))
 out[actor]=results
(p/('RecoveryKnee-'+tag+'.json')).write_text(json.dumps(out,indent=2))
for a,v in out.items():
 print(a,'worst physical',json.dumps(v['PhysicalMesh']['worst'][:6],indent=2))
