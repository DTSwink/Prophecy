"""Brief owned TestNN Play initialization check; no tuning or asset writes."""
import json
from pathlib import Path
import time
import unreal


def start_contact_smoke():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if editor.get_game_world():
        raise RuntimeError('User Play is active; leaving it untouched.')
    if editor.get_editor_world().get_path_name() != '/Game/testNN.testNN':
        raise RuntimeError('Expected the preserved TestNN map.')
    output = Path(unreal.Paths.project_saved_dir())/'Diagnostics/RobotLocomotion20261026/contact-play.json'
    state = dict(world=None, frames=0, start=time.monotonic(), callback=None)

    def finish(error=None):
        unreal.unregister_slate_post_tick_callback(state['callback'])
        if state['world'] and editor.get_game_world() == state['world']:
            level.editor_request_end_play()
        result = dict(success=error is None, error=error, observed_frames=state['frames'],
                      actors=state.get('actors', []), saved_assets=False)
        output.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print('ROBOT_CONTACT_PLAY', json.dumps(result))

    def tick(_):
        try:
            world = editor.get_game_world()
            if world:
                if state['world'] is None:
                    state['world'] = world
                    agents = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
                    state['actors'] = [a.get_path_name() for a in agents]
                    if not agents:
                        finish('No agents initialized in TestNN.')
                        return
                elif world != state['world']:
                    finish('Play world changed during verification.')
                    return
                state['frames'] += 1
                if state['frames'] >= 12:
                    finish()
                    return
            elif state['world']:
                finish('Play ended before verification finished.')
                return
            if time.monotonic()-state['start'] > 30:
                finish('Play initialization timed out.')
        except Exception as exc:
            finish(str(exc))

    state['callback'] = unreal.register_slate_post_tick_callback(tick)
    level.editor_request_begin_play()
    print('Requested a brief owned Play initialization check.')


start_contact_smoke()
