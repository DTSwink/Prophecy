import json,math,re
from pathlib import Path
p=Path(__file__).parent
def read(tag):
 d=json.loads((p/(tag+'.json')).read_text());assert not d['error'],d['error']
 return {r['tick']:r for r in d['rows'] if r['player']}
def angle(a,b):return math.degrees(2*math.acos(min(1,abs(sum(x*y for x,y in zip(a,b))))))
def wrap(a):return (a+180)%360-180
a,b=read('wrap_periodic_before'),read('wrap_periodic_after')
out={'position_error_cm':max(math.dist(a[t][phase][bone]['p'],b[t][phase][bone]['p']) for t in a for phase in ['future','presented'] for bone in ['upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r']),
 'left_rotation_error_degrees':max(angle(a[t]['future']['hand_l']['q'],b[t]['future']['hand_l']['q']) for t in a), 'traces':{}}
for tag in ['before','after']:
 log=(p/('wrap_periodic_'+tag+'.log')).read_text(errors='replace')
 pattern=r'WristTwist time=([\d.]+) weight=([\d.]+) previous=([\d.-]+) proposed=([\d.-]+) accepted=([\d.-]+) actual=([\d.-]+)'
 rows=[dict(zip(['time','weight','previous','proposed','accepted','actual'],map(float,m))) for m in re.findall(pattern,log)]
 inside=[r for r in rows if abs(wrap(r['proposed']))<5]
 out['traces'][tag]={'within_limit_samples':len(inside),'max_correction_for_within_limit_proposal':max(abs(wrap(r['actual']-r['proposed'])) for r in inside),
  'max_solver_error':max(abs(r['actual']-r['accepted']) for r in rows),'samples':{}}
 for r in rows:
  tick=round(r['time']*60)
  if tick in [191,205,221,249,251,259,269,271,301,341]:
   out['traces'][tag]['samples'][tick]={'proposed':wrap(r['proposed']),'actual':wrap(r['actual'])}
assert out['position_error_cm']<1e-4
assert out['traces']['after']['max_correction_for_within_limit_proposal']<1e-4
assert all(math.isfinite(v) for r in b.values() for phase in ['future','presented'] for bone in r[phase].values() for k in ['p','q'] for v in bone[k])
(p/'periodic_analysis.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
