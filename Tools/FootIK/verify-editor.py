"""Owned cold-editor reflection/Play check, dispatched through UE remote Python.

No Blueprint wiring/defaults or assets are edited or saved. This only tests
startup and the public disabled node; live motion has separate native tests.
"""
import hashlib
import json
import pathlib
import time
import traceback
import unreal

root = pathlib.Path(unreal.Paths.project_dir()).resolve()
assert root.name == 'NativeHost' and root.parent.name == 'FootIKPort20261030'
assert '-FootIKEditorCheck' in unreal.SystemLibrary.get_command_line()
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not editor.get_game_world(), 'An existing Play session is never interrupted.'
assert '/Game/testNN' in editor.get_editor_world().get_path_name()
out = root / 'Saved/Diagnostics/FootIKPort20261030/editor-check.json'
assets = ['Content/_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset', 'Content/testNN.umap']
hashes = lambda: {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in assets}
state = dict(start=time.monotonic(), before=hashes(), world=None, rows=[], first_tick=None)
api = unreal.get_default_object(unreal.load_class(None, '/Script/GameAnimationSample3.ProphecyFootIKLiveLibrary'))
assert api, 'Foot IK Blueprint library missing after cold build'
bp = unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
assert bp
unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'Prophecy.Editor.LiveAgentTypes Inspect')

def finish(success, reason):
    unreal.unregister_slate_post_tick_callback(state['callback'])
    world = editor.get_game_world()
    if world and world == state['world']:
        level.editor_request_end_play()
    after = hashes()
    result = dict(success=success and after == state['before'], reason=reason,
                  scope='Cold reflection and NN Play startup; physical tracking is tested separately',
                  assets_unchanged=after == state['before'], before=state['before'], after=after,
                  rows=state['rows'], disabled_node=state.get('disabled_node'),
                  elapsed_seconds=time.monotonic() - state['start'])
    out.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('FOOTIK_EDITOR_CHECK', json.dumps(result))

def tick(_):
    try:
        if time.monotonic() - state['start'] > 180:
            return finish(False, 'Owned Play initialization timed out')
        world = editor.get_game_world()
        if not world:
            return
        state['world'] = world
        actor = unreal.GameplayStatics.get_player_pawn(world, 0)
        if not isinstance(actor, unreal.ProphecyAgent):
            return
        n = int(actor.get_editor_property('absolute tick debug'))
        if state['first_tick'] is None:
            state['first_tick'] = n
            state['disabled_node'] = str(api.call_method('SetFootIKEnabled', args=(actor, False)))
        if state['rows'] and n == state['rows'][-1]['absolute_tick']:
            return
        names, future, current, alpha = actor.read_nn_future_world_pose()
        if len(names) < 25 or len(current) != len(names):
            return
        if len(state['rows']) < 5 or n - state['first_tick'] >= 60:
            state['rows'].append(dict(absolute_tick=n, bones=len(names), alpha=float(alpha), actor=actor.get_path_name()))
        if n - state['first_tick'] >= 60:
            finish(True, 'Existing Blueprint compiled; actual Play initialized and NN targets advanced')
    except Exception:
        finish(False, traceback.format_exc())

state['callback'] = unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('FOOTIK_EDITOR_CHECK_STARTED')
