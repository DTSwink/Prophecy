"""Transient correctness smoke test. No assets changed and no timing benchmark."""
import builtins
import json
import math
import pathlib
import traceback
import unreal

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world()
# Never attach this mutating test to the user's Play session.
editor_guard = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert editor_guard.get_game_world() is None, 'Stop your Play session before running this test'
import time
owned_world = None
watchdog_start = time.monotonic()
finished = False
diagnostic_ticks = 0
last_world_time = None

state = dict(actors=[], phase=0, samples=0, events=[])
builtins._nn_interpolation_check = state

def finish(reason):
    global finished
    if finished: return
    finished = True
    unreal.unregister_slate_post_tick_callback(state['callback'])
    path = pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics/SlashContacts/InterpolationSmoke.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(reason=reason, samples=state['samples'], events=state['events'])), encoding='utf-8')
    if owned_world is not None and editor_guard.get_game_world() == owned_world:
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('NN_INTERPOLATION_CHECK', reason)

def tick(_):
    global owned_world, diagnostic_ticks, last_world_time
    try:
        if time.monotonic() - watchdog_start > 60:
            raise RuntimeError('Diagnostic timed out (Play failed, stopped, or paused)')
        current_world = editor_guard.get_game_world()
        if owned_world is not None and current_world != owned_world:
            raise RuntimeError('Owned Play session ended or was replaced')
        if current_world is not None and owned_world is None:
            owned_world = current_world
        if current_world is not None:
            stamp = unreal.GameplayStatics.get_time_seconds(current_world)
            if stamp != last_world_time:
                last_world_time = stamp
                if not unreal.GameplayStatics.is_game_paused(current_world): diagnostic_ticks += 1
        world = editor.get_game_world()
        if not world:
            return
        now = diagnostic_ticks / 60.0
        current = unreal.ProphecyNNInterpolationMode.CURRENT
        cubic = unreal.ProphecyNNInterpolationMode.HERMITE_SLERP
        if not state['actors']:
            state['actors'] = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent) if a.get_agent_handle().index in (0, 2)]
            assert len(state['actors']) == 2
            for actor in state['actors']:
                assert actor.get_nn_interpolation_mode() == current
                actor.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
                actor.set_actor_tick_enabled(False)
                actor.stop_nn_attack()
            state['actors'][0].set_nn_interpolation_mode(cubic)
            assert state['actors'][0].get_nn_interpolation_mode() == cubic
            assert state['actors'][1].get_nn_interpolation_mode() == current
            state['events'].append('Default and per-agent selection verified')
        if now < 0.8:
            for actor in state['actors']:
                actor.stop_nn_attack()
        if now >= 1 and state['phase'] == 0:
            for i, actor in enumerate(state['actors']):
                actor.set_nn_interpolation_mode(cubic)
                assert actor.trigger_nn_attack('hookR', actor.get_root_low_point() + unreal.Vector(-30, 50, 115), bool(i))
            state['phase'] = 1
            state['events'].append('Full and half attacks started in new mode')
        if now >= 2 and state['phase'] == 1:
            for actor in state['actors']:
                actor.stop_nn_attack()
                actor.set_nn_interpolation_mode(current)
                assert actor.get_nn_interpolation_mode() == current
            state['phase'] = 2
            state['events'].append('Returned to locomotion and current mode')
        for actor in state['actors']:
            pose = actor.read_nn_future_world_pose()
            if not pose:
                continue
            names, future, shown, alpha = pose
            assert len(names) == len(future) == len(shown) and len(names) > 0
            assert 0 <= alpha <= 1
            for transform in shown:
                p, q = transform.translation, transform.rotation
                assert all(math.isfinite(v) for v in (p.x,p.y,p.z,q.x,q.y,q.z,q.w))
            state['samples'] += 1
        if now >= 3:
            assert state['samples'] > 10
            finish('passed')
    except Exception:
        finish(traceback.format_exc())

state['callback'] = unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
