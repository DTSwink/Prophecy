"""Checks the actual recorded bone poses, not just successful test completion."""
import json,pathlib,math
p=pathlib.Path(__file__).resolve().parents[2]/'Saved/Diagnostics/HolsterStrap20261013'
d=json.loads((p/'probe.json').read_text());assert d['reason']=='completed',d['reason']
rows=d['rows'];rest=d['rest']
def distance(a,b):return math.dist(a[:3],b[:3])
assert distance(rest['strap_01'],rest['strap_tip'])>10,'Missing or incorrectly scaled rig'
report={'samples':len(rows),'events':d['events']}
for lo,hi,label,ticking in [(0,4,'initial_off',False),(80,109,'manual_off',False),(165,184,'distance_off',True),(235,249,'global_off',True),(310,335,'final_off',False)]:
 window=[r for r in rows if lo<=r['t']<=hi];assert window,label
 assert all(not r['running'] and r['component_tick']==ticking for r in window),label
 error=max(distance(r['bones'][b],v) for r in window for b,v in rest.items())
 assert error<.001,(label,error)
 report[label+'_rest_error_cm']=error
for lo,hi,label in [(20,79,'initial_on'),(125,149,'manual_on'),(200,219,'distance_on'),(265,279,'global_on'),(285,309,'teleport')]:
 window=[r for r in rows if lo<=r['t']<=hi];assert window,label
 assert all(r['running'] and r['component_tick'] for r in window),label
 motion=max(distance(r['bones']['strap_tip'],rest['strap_tip']) for r in window)
 assert .01<motion<33,(label,motion) # Twice the approximately 16 cm free-tail length.
 fixed=max(distance(r['bones']['strap_root'],rest['strap_root']) for r in window)
 assert fixed<.001,(label,'fixed leather root',fixed)
 anchor=max(distance(r['bones']['strap_01'],rest['strap_01']) for r in window)
 # The first dynamic joint is approximate; the wrapped leather uses strap_root.
 assert anchor<.3,(label,anchor)
 report[label]={'tip_deflection_cm':motion,'dynamic_joint_error_cm':anchor,'fixed_root_error_cm':fixed}
assert all('NO_COLLISION' in r['collision'] for r in rows)
if d.get('settle'):
 late=[distance(r['bones']['strap_tip'],rows[i-1]['bones']['strap_tip']) for i,r in enumerate(rows) if 600<r['tick']-d['spawn']<675]
 assert late and max(late)<.01,('stationary strap must settle',max(late) if late else None)
 report['settled_peak_tip_travel_cm_per_tick']=max(late)
(p/'verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
