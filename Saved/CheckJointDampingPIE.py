import unreal, time, json
from pathlib import Path

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not editor.get_game_world(), 'Run this check with PIE stopped'
assert unreal.load_class(None, '/Script/GameAnimationSample3.ProphecyJointDampingLibrary')
state = dict(start=time.monotonic(), frames=0)
result_path = Path(unreal.Paths.project_saved_dir()) / 'Diagnostics/JointDampingPIE.json'

def check(delta):
    world = editor.get_game_world()
    if world:
        state['frames'] += 1
        if state['frames'] == 1:
            state['world'] = world.get_path_name()
    if state['frames'] >= 120 or time.monotonic() - state['start'] > 45:
        unreal.unregister_slate_post_tick_callback(state['callback'])
        result = dict(success=state['frames'] >= 120, frames=state['frames'], world=state.get('world'))
        if world:
            level.editor_request_end_play()
        result_path.write_text(json.dumps(result, indent=2))
        print('Joint damping PIE startup check: ' + json.dumps(result))

state['callback'] = unreal.register_slate_post_tick_callback(check)
level.editor_request_begin_play()
print('Requested a short PIE world-creation check; it will stop automatically')
