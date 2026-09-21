import builtins
import json
import unreal
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
a = unreal.GameplayStatics.get_player_pawn(w, 0) if w else None
s = getattr(builtins, '_prophecy_pelvis_backward_capture', {})
print(json.dumps({'pie_running': bool(w), 'agent': a.get_actor_label() if a else None,
                  'capture_done': s.get('done'), 'capture_callback_removed': not s.get('handle'),
                  'pelvis_feedback': str(a.get_physical_feedback_tolerance('pelvis')) if a else None,
                  'self_collision': str(a.get_jolt_body_pair_self_collision_enabled('hand_l','head')) if a else None,
                  'sword': str(a.get_held_sword()) if a else None,
                  'input': str(a.get_editor_property('locomotion_input')) if a else None}, indent=2))
