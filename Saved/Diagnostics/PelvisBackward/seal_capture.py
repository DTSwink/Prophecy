import builtins
import json
import pathlib
import unreal
s = getattr(builtins, '_prophecy_pelvis_backward_capture', None)
if s:
    if s.get('handle'):
        unreal.unregister_slate_post_tick_callback(s['handle'])
        s['handle'] = None
    s['done'] = True
    a = s.get('actor')
    if a:
        s['settings_at_seal'] = {'feedback_pelvis':str(a.get_physical_feedback_tolerance('pelvis')),
            'self_collision_hand_head':str(a.get_jolt_body_pair_self_collision_enabled('hand_l','head')),
            'sword':str(a.get_held_sword()), 'input':str(a.get_editor_property('locomotion_input'))}
    payload = {k:v for k,v in s.items() if k not in ('actor','mesh','handle','finish')}
    pathlib.Path(s['path']).write_text(json.dumps(payload, separators=(',', ':')), encoding='utf-8')
    print('SEALED', len(s['rows']), s['path'])
