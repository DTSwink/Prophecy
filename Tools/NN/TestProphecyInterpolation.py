"""Transient correctness smoke test. No assets changed and no timing benchmark."""
import builtins
import json
import math
import pathlib
import traceback
import unreal

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world()
state = dict(actors=[], phase=0, samples=0, events=[])
builtins._nn_interpolation_check = state

def finish(reason):
    unreal.unregister_slate_post_tick_callback(state['callback'])
    path = pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics/SlashContacts/InterpolationSmoke.json'
    path.write_text(json.dumps(dict(reason=reason, samples=state['samples'], events=state['events'])), encoding='utf-8')
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('NN_INTERPOLATION_CHECK', reason)

def tick(_):
    try:
        world = editor.get_game_world()
        if not world:
            return
        now = unreal.GameplayStatics.get_time_seconds(world)
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
