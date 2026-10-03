import json,math,re
from pathlib import Path
p=Path(__file__).parent
def mul(a,b):
 x,y,z,w=a;X,Y,Z,W=b
 return [w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z]
def inv(q):return [-q[0],-q[1],-q[2],q[3]]
def local(r,phase='future'):return mul(inv(r[phase]['spine_05']['q']),r[phase]['hand_r']['q'])
def angular(a,b):return math.degrees(2*math.acos(min(1,abs(sum(x*y for x,y in zip(a,b))))))
def read(tag):
 d=json.loads((p/(tag+'.json')).read_text());assert not d['error'],d['error']
 return {r['tick']:r for r in d['rows'] if r['player']}
a,b=read('wrap_idle_before'),read('wrap_idle_after')
log=(p/'wrap_idle_after.log').read_text(errors='replace')
refs=re.findall(r'WristIdleReference q=([\d.,-]+) axis=([\d.,-]+)',log)
assert len(refs)==1,refs
q,axis=([float(v) for v in s.split(',')] for s in refs[0])
def twist(r,phase='future'):
 d=mul(local(r,phase),inv(q));v=sum(d[i]*axis[i] for i in range(3))
 return (math.degrees(2*math.atan2(v,d[3]))+180)%360-180
out=dict(reference=q,axis=axis,idle_decodes=len(refs),samples={})
for t in [1,190,191,195,210,230,250,270,300,340]:
 out['samples'][t]={name:{'twist_idle_deg':twist(r[t]),'presented_twist_idle_deg':twist(r[t],'presented'),'whole_rotation_idle_deg':angular(local(r[t]),q)} for name,r in [('before',a),('after',b)]}
out['max_joint_position_difference_cm']=max(math.dist(a[t][phase][bone]['p'],b[t][phase][bone]['p']) for t in a for phase in ['future','presented'] for bone in ['upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r'])
out['max_left_rotation_difference_degrees']=max(angular(a[t]['future']['hand_l']['q'],b[t]['future']['hand_l']['q']) for t in a)
out['max_abs_twist_230_300']=max(abs(twist(b[t])) for t in b if 230<=t<=300)
errors=[abs(float(m[0])-float(m[1])) for m in re.findall(r'accepted=([\d.-]+) actual=([\d.-]+)',log)]
out['max_solver_twist_error_deg']=max(errors)
assert all(math.isfinite(v) for r in b.values() for phase in ['future','presented'] for bone in r[phase].values() for k in ['p','q'] for v in bone[k])
(p/'idle_reference_analysis.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
