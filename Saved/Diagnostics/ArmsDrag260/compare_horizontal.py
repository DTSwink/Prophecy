import json,math
from pathlib import Path
p=Path(__file__).parent
def mul(a,b):
 x,y,z,w=a;X,Y,Z,W=b
 return [w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z]
def inv(q):return [-q[0],-q[1],-q[2],q[3]]
def rot(q,v):return mul(mul(q,[*v,0]),inv(q))[:3]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def local(r,phase='future'):return mul(inv(r[phase]['spine_05']['q']),r[phase]['hand_r']['q'])
def angle(a,b):return math.degrees(2*math.acos(min(1,abs(dot(a,b)))))
def read(tag):
 d=json.loads((p/(tag+'.json')).read_text());assert not d['error'];return {x['tick']:x for x in d['rows'] if x['player']}
a,b=read('wrap_forward_blade_before'),read('wrap_horizontal_clamp')
g=json.loads((p/'wrap_forward_blade_before_heading.json').read_text());up,forward,blade=g['up'],g['forward'],g['blade_axis']
def heading(r,phase):
 if phase=='actual':
  w=r['weapon'];aim=rot(mul(inv(r['presented']['spine_05']['q']),w['actual']['q']),rot(inv(w['grip']['q']),blade))
 else:aim=rot(local(r,phase),blade)
 flat=[x-dot(aim,up)*y for x,y in zip(aim,up)]
 return math.degrees(math.atan2(dot(up,cross(forward,flat)),dot(forward,flat)))
out={'position_difference_cm':max(math.dist(a[t][ph][bone]['p'],b[t][ph][bone]['p']) for t in a for ph in ['future','presented'] for bone in ['upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r']),
 'left_rotation_difference_deg':max(angle(a[t]['future']['hand_l']['q'],b[t]['future']['hand_l']['q']) for t in a),'motion':{}}
for tag,rr in [('before',a),('after',b)]:
 out['motion'][tag]={'samples':{t:{ph:heading(rr[t],ph) for ph in ['future','presented','actual']} for t in [191,201,211,221,225,227,229,251,269,301,341]},
  'max_abs_heading_205_330':{ph:max(abs(heading(rr[t],ph)) for t in rr if 205<=t<=330) for ph in ['future','presented','actual']},
  'wrist_step_at227':angle(local(rr[227]),local(rr[225])),
  'max_wrist_step_215_235':max((angle(local(rr[t]),local(rr[t-2])),t) for t in rr if t%2 and 215<=t<=235)}
out['release_max_tick_rotation_339_380']=max((angle(local(b[t],'presented'),local(b[t-1],'presented')),t) for t in b if 339<=t<=380)
assert out['position_difference_cm']<.0001
assert out['motion']['after']['max_abs_heading_205_330']['future']<5.01
# Quaternion interpolation between NN samples can overshoot the projected heading slightly.
assert out['motion']['after']['max_abs_heading_205_330']['actual']<6
assert all(math.isfinite(v) for r in b.values() for ph in ['future','presented'] for bone in r[ph].values() for k in ['p','q'] for v in bone[k])
(p/'horizontal_clamp_analysis.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))

