import builtins
import json
import math
import pathlib
s = getattr(builtins, '_prophecy_pelvis_backward_capture', {})
rows = s.get('rows', [])
actor = s.get('actor')
if actor:
    print('CURRENT_SETTINGS', str(actor.get_physical_feedback_tolerance('pelvis')),
          str(actor.get_jolt_body_pair_self_collision_enabled('hand_l','head')),
          str(actor.get_held_sword()), str(actor.get_editor_property('locomotion_input')))
events = []
for i in range(1, len(rows)):
    a, b = rows[i-1:i+1]
    speed = math.hypot(b['mover_v'][0], b['mover_v'][1])
    if speed < 20:
        continue
    d = [b['mover_v'][0]/speed, b['mover_v'][1]/speed]
    steps = {k: sum((b[k][j]-a[k][j])*d[j] for j in range(2)) for k in ('capsule','target','future','body','visible')}
    if min(steps['body'], steps['capsule'], steps['target']) < -0.1:
        events.append({'i':i, 't':b['t'], 'previous_dt':a['dt'], 'dt':b['dt'],
                       'alpha_before':a['alpha'], 'alpha_after':b['alpha'], **steps})
print(json.dumps({'count':len(rows), 'done':s.get('done'), 'error':s.get('error'), 'metadata':s.get('metadata'),
                 'time':rows[-1]['t'] if rows else None, 'first':rows[0] if rows else None,
                 'events_count':len(events), 'events':events[:12]}, indent=2))
if s.get('done'):
    payload = {k:v for k,v in s.items() if k not in ('actor','mesh','handle','finish')}
    pathlib.Path(s['path']).write_text(json.dumps(payload, separators=(',', ':')), encoding='utf-8')
