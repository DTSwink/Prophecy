"""Transient PIE checks for input debugging, root windows and attack handoff. No asset writes."""
import builtins
import json
import math
import pathlib
import time
import traceback
import unreal

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world()
state = dict(actors=[], last=-1, phase=-1, events=[], rows=[], wall=time.perf_counter())
builtins._nn_controls_check = state


def transform(value):
    p, q = value.translation, value.rotation
    return [p.x, p.y, p.z, q.x, q.y, q.z, q.w]


def finish(reason):
    unreal.unregister_slate_post_tick_callback(state['callback'])
    world = editor.get_game_world()
    if world:
        unreal.SystemLibrary.execute_console_command(world, 'Prophecy.NNInputTraceFrames 0')
    path = pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics/SlashContacts/LocomotionControls.json'
    path.write_text(json.dumps(dict(reason=reason, events=state['events'], rows=state['rows'])), encoding='utf-8')
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('NN_CONTROLS_CHECK', reason)


def tick(_):
    try:
        world = editor.get_game_world()
        if not world:
            return
        now = unreal.GameplayStatics.get_time_seconds(world)
        if now == state['last']:
            return
        state['last'] = now
        if not state['actors']:
            state['actors'] = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent) if a.get_agent_handle().index in (0, 2)]
            assert state['actors']
            for index, actor in enumerate(state['actors']):
                actor.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
                actor.set_actor_tick_enabled(False)
                actor.stop_nn_attack()
                actor.set_locomotion_input(unreal.Vector(0, float(index == 1), 0), False, unreal.Vector(0, 1, 0), 1, 1)
                for part in ('foot', 'calf', 'hand'):
                    setter = getattr(actor, 'set_locomotion_' + part + '_clamp')
                    assert setter(True, 1)
                    assert not setter(True, -1)
                    assert setter(False, 0)
                actor.set_attack_foot_clamp(False, 0)
                actor.set_attack_calf_clamp(False, 0)
                mesh = actor.set_show_nn_previous_pose_debug_mesh(True, bool(index % 2))
                assert mesh and actor.get_editor_property('nn_previous_pose_debug_mesh') == mesh
                assert not mesh.is_component_tick_enabled()
                mesh.set_material(0, actor.get_pose_reference_mesh().get_material(0))
            for manager in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyNNLocomotionManager):
                for prop in ('clamp_foot', 'clamp_calf', 'clamp_hand'):
                    manager.set_editor_property(prop, False)
            unreal.SystemLibrary.execute_console_command(world, 'Prophecy.NNInputTraceFrames 300')
            state['phase'] = 0
        # Stop initialization attacks before the controlled episode; never modify assets.
        if now < 0.8:
            for actor in state['actors']:
                actor.stop_nn_attack()
        if now >= 1 and state['phase'] == 0:
            for index, actor in enumerate(state['actors']):
                target = actor.get_root_low_point() + unreal.Vector(-30, 50, 115)
                assert actor.trigger_nn_attack('hookR', target, bool(index % 2))
            state['phase'] = 1
        if now >= 3 and state['phase'] == 1:
            # Second episode: explicit interruption rather than automatic learned completion.
            for index, actor in enumerate(state['actors']):
                actor.stop_nn_attack()
                assert actor.trigger_nn_attack('slashL', actor.get_root_low_point() + unreal.Vector(40, 70, 110), not bool(index % 2))
            state['phase'] = 2
        if now >= 3.25 and state['phase'] == 2:
            for actor in state['actors']:
                before = actor.read_nn_future_world_pose()
                actor.stop_nn_attack()
                after = actor.read_nn_future_world_pose()
                assert before and after
                errors = [math.dist(transform(a)[:3], transform(b)[:3]) for a, b in zip(before[1], after[1])]
                assert max(errors) < 0.001, (actor.get_name(), 'stop changed world pose', max(errors))
                state['events'].append(dict(actor=actor.get_name(), stop_world_pose_error_cm=max(errors)))
            state['phase'] = 3
        for actor in state['actors']:
            result = actor.get_locomotion_root_window()
            if now > 0.2:
                assert result
                roots, times = result
                assert len(roots) == len(times) == 10 and times[0] < 0 and times[1] == 0
                assert all(a < b for a, b in zip(times, times[1:]))
                assert all(math.isfinite(v) for root in roots for v in transform(root))
            pose = actor.read_nn_future_world_pose()
            if not pose:
                continue
            names, future, shown, alpha = pose
            state['rows'].append(dict(t=now, actor=actor.get_name(), attack=str(actor.get_nn_attack_state()),
                future={str(n): transform(v) for n, v in zip(names, future)},
                shown={str(n): transform(v) for n, v in zip(names, shown)}))
        if now >= 4 and state['phase'] == 3:
            for actor in state['actors']:
                actor.set_show_nn_previous_pose_debug_mesh(False)
                assert actor.get_editor_property('nn_previous_pose_debug_mesh') is None
                # Re-enable to catch lifecycle/duplicate-name mistakes.
                assert actor.set_show_nn_previous_pose_debug_mesh(True, False)
                actor.set_show_nn_previous_pose_debug_mesh(False)
            state['phase'] = 4
        if now >= 6:
            assert state['phase'] == 4
            finish('Complete')
        elif time.perf_counter() - state['wall'] > 180:
            finish('Timeout')
    except Exception:
        finish(traceback.format_exc())


state['callback'] = unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()

