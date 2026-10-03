import json,pathlib,math,sys
p=pathlib.Path(__file__).parent
tag=sys.argv[1] if len(sys.argv)>1 else 'wrap_before'
rows={r['tick']:r for r in json.loads((p/(tag+'.json')).read_text())['rows'] if r['player']}
def mul(a,b):
 x,y,z,w=a;X,Y,Z,W=b
 return [w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z]
def inv(q):return [-q[0],-q[1],-q[2],q[3]]
def local(r):return mul(inv(r['future']['spine_05']['q']),r['future']['hand_r']['q'])
def unwrap(a,b):return b+(a-b+math.pi)%(2*math.pi)-math.pi
reference=local(rows[182]);prev=reference;last=0;result=[]
for t,r in rows.items():
 if t<183:continue
 q=local(r);d=mul(q,inv(reference));angle=unwrap(2*math.atan2(d[0],d[3]),last);last=angle
 step=math.degrees(2*math.acos(min(1,abs(sum(x*y for x,y in zip(q,prev))))));prev=q
 if t%2==1:result.append(dict(t=t,angle=round(math.degrees(angle),3),step=round(step,3),q=q))
print('Largest right wrist spine-local steps', sorted(result,key=lambda r:r['step'],reverse=True)[:8])
print('Angles',[(r['t'],r['angle'],r['step']) for r in result if r['t']<=275])
(p/(tag+'_angles.json')).write_text(json.dumps(result,indent=2))
