import json
import pathlib
import unreal
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
info = {'pie_was_running': bool(w)}
if w:
    a = unreal.GameplayStatics.get_player_pawn(w, 0)
    if isinstance(a, unreal.ProphecyAgent):
        info.update({'agent':a.get_actor_label(), 'input':str(a.get_editor_property('locomotion_input')),
                     'pelvis_feedback':str(a.get_physical_feedback_tolerance('pelvis')),
                     'self_collision':str(a.get_jolt_body_pair_self_collision_enabled('hand_l','head')),
                     'held_sword':str(a.get_held_sword())})
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
p = pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'/'PelvisBackward'/'pre-fix-state.json'
p.write_text(json.dumps(info,indent=2),encoding='utf-8')
print(json.dumps(info))
