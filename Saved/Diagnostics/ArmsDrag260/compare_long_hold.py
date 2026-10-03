import pathlib,json,math,re
p=pathlib.Path(__file__).parent
def read(tag):
 d=json.loads((p/(tag+'.json')).read_text());assert not d['error'],d['error']
 return {r['tick']:r for r in d['rows'] if r['player']}
def mul(a,b):
 x,y,z,w=a;X,Y,Z,W=b
 return [w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z]
def local(r):
 s=r['future']['spine_05']['q'];return mul([-s[0],-s[1],-s[2],s[3]],r['future']['hand_r']['q'])
def deg(a,b):return math.degrees(2*math.acos(min(1,abs(sum(x*y for x,y in zip(a,b))))))
a,b=read('wrap_long270'),read('wrap_long270_fixed')
out={
 'max_joint_position_difference_cm':max(math.dist(a[t][phase][bone]['p'],b[t][phase][bone]['p']) for t in a for phase in ['future','presented'] for bone in ['upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r']),
 'max_left_rotation_difference_degrees':max(deg(a[t]['future']['hand_l']['q'],b[t]['future']['hand_l']['q']) for t in a),
 'right_steps':{},
 'right_rotation_difference_at270_degrees':deg(local(a[270]),local(b[270]))}
for tag,rr in [('before',a),('after',b)]:
 steps=[(deg(local(rr[t]),local(rr[t-2])),t) for t in rr if 235<=t<=280 and t%2]
 out['right_steps'][tag]={'max_235_280':max(steps),'at249':deg(local(rr[249]),local(rr[247])),'at251':deg(local(rr[251]),local(rr[249]))}
errors=[]
for line in (p/'wrap_long270_fixed.log').read_text(errors='replace').splitlines():
 m=re.search(r'accepted=([\d.-]+) actual=([\d.-]+)',line)
 if m:errors.append(abs(float(m[1])-float(m[2])))
out['max_reported_twist_error_degrees']=max(errors)
print(json.dumps(out,indent=2));(p/'long_hold_analysis.json').write_text(json.dumps(out,indent=2))
