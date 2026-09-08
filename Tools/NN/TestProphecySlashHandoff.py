"""PIE-only numerical handoff/forearm regression. No screenshots or asset saves."""
import json
import math
import time
import traceback
from pathlib import Path
import unreal

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_game_world() or unreal.EditorLevelLibrary.get_game_world()
assert world, 'Start testNN PIE first'
agents = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
actor = next(a for a in agents if a.get_agent_handle().index == 1)
original_mode = actor.get_simulation_mode()
original_input = actor.get_locomotion_input()
original_override = actor.get_editor_property('use_blueprint_locomotion_input')
original_fps = unreal.SystemLibrary.get_console_variable_float_value('t.MaxFPS')
actor.call_method('StopNNAttack')
assert actor.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
actor.stop_locomotion_input()
mesh = actor.get_pose_reference_mesh()
manager = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyNNLocomotionManager)[0]
original_debug = actor.get_editor_property('show_kinematic_debug_mesh')
actor.set_show_kinematic_debug_mesh(True)
cases = [(60, 'stop', False), (60, 'replace', False), (5, 'stop', False),
         (5, 'replace', False), (60, 'natural', False), (60, 'stop', True)]
state = {'handle': None, 'case': -1, 'phase': 'start', 'deadline': time.monotonic()+0.5,
         'rows': [], 'events': [], 'metrics': [], 'last_frame': -1}
output = Path(unreal.Paths.project_saved_dir()).resolve() / 'SlashParity/root_handoff.json'


def xyz(v):
    return [v.x, v.y, v.z]


def read():
    names, future, presented, alpha = actor.read_nn_future_world_pose()
    target = {str(n): xyz(t.translation) for n, t in zip(names, future)}
    display = {str(n): xyz(t.translation) for n, t in zip(names, presented)}
    realized = {str(n): xyz(mesh.get_socket_transform(n, unreal.RelativeTransformSpace.RTS_WORLD).translation) for n in names}
    error = max(math.dist(display[n], realized[n]) for n in display)
    core_error = max(math.dist(display[n], realized[n]) for n in display
                     if not n.startswith(('calf_', 'foot_', 'ball_')))
    debug = next((c for c in manager.get_components_by_class(unreal.PoseableMeshComponent)
                  if c.get_name() == 'KinematicDebugMesh_1'), None)
    debug_pose = {str(n): xyz(debug.get_socket_transform(n, unreal.RelativeTransformSpace.RTS_WORLD).translation) for n in names} if debug else {}
    return {'root': xyz(actor.get_root_low_point()), 'future': target, 'presented': display,
            'realized': realized, 'debug': debug_pose, 'render_error_cm': error,
            'core_error_cm': core_error, 'alpha': alpha}


def finish(error=None):
    if state['handle'] is not None:
        unreal.unregister_slate_post_tick_callback(state['handle'])
        state['handle'] = None
    actor.call_method('StopNNAttack')
    actor.set_locomotion_input(original_input.world_move_input, original_input.run,
        original_input.facing_world_direction, original_input.speed_scale, original_input.turn_scale)
    actor.set_editor_property('use_blueprint_locomotion_input', original_override)
    actor.set_simulation_mode(original_mode)
    actor.set_show_kinematic_debug_mesh(original_debug)
    unreal.SystemLibrary.execute_console_command(world, f't.MaxFPS {original_fps}')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'passed': error is None, 'error': error,
        'actor': actor.get_name(), 'events': state['events'], 'metrics': state['metrics'], 'samples': state['rows']}, indent=2))
    print('Root/forearm handoff audit:', output, 'error=', error)


def event(kind, function):
    before = read()
    assert function(), kind + ' failed'
    after = read()
    row = {'case': state['case'], 'kind': kind,
           'root_shift_cm': math.dist(before['root'], after['root']),
           'future_jump_cm': max(math.dist(before['future'][n], after['future'][n]) for n in before['future']),
           'presented_jump_cm': max(math.dist(before['presented'][n], after['presented'][n]) for n in before['presented']),
           'mesh_jump_cm': max(math.dist(before['realized'][n], after['realized'][n]) for n in before['realized']),
           'debug_jump_cm': max(math.dist(before['debug'][n], after['debug'][n]) for n in before['debug']),
           'before_render_error_cm': before['render_error_cm'], 'after_render_error_cm': after['render_error_cm']}
    state['events'].append(row)
    assert row['future_jump_cm'] < 0.001, row
    assert row['presented_jump_cm'] < 0.001, row
    assert after['core_error_cm'] < 0.1, row
    assert row['mesh_jump_cm'] < 0.1, row
    assert row['debug_jump_cm'] < 0.001, row
    if not cases[state['case']][2]:
        assert row['root_shift_cm'] > 0.01, row
    else:
        assert row['root_shift_cm'] < 0.001, row


def tick(_delta):
    try:
        now = time.monotonic()
        if state['phase'] == 'start':
            if now < state['deadline']: return
            state['case'] += 1
            if state['case'] == len(cases):
                finish(); return
            fps, kind, half = cases[state['case']]
            unreal.SystemLibrary.execute_console_command(world, f't.MaxFPS {fps}')
            state['origin'] = read()
            state['target'] = actor.get_actor_transform().transform_location(unreal.Vector(-45, 110, 10))
            assert actor.call_method('TriggerNNAttack', args=(unreal.Name('slashL'), state['target'], half))
            state['phase'] = 'attack'
            state['last_frame'] = -1
            state['deadline'] = now + 20
        current = actor.call_method('GetNNAttackState')
        row = read()
        row['case'] = state['case']
        row['attack'] = str(current)
        state['rows'].append(row)
        if state['phase'] == 'after':
            assert row['core_error_cm'] < 0.1, ('post handoff mismatch', row['core_error_cm'])
            if now >= state['deadline']:
                state['phase'] = 'start'; state['deadline'] = now + 0.1
            return
        assert now < state['deadline'], 'Attack did not finish'
        fps, kind, half = cases[state['case']]
        if current is None:
            assert kind == 'natural', 'Unexpected completion before test event'
            shift = math.dist(state['origin']['root'], row['root'])
            state['metrics'].append({'case': state['case'], 'natural_root_shift_cm': shift})
            assert shift > 0.01
            state['phase'] = 'after'; state['deadline'] = now + 0.4
            return
        frame = current[-1]
        if frame >= 3:
            for side, expected in [('l', 22.349145889282227), ('r', 22.3492431640625)]:
                for field in ['future', 'presented']:
                    length = math.dist(row[field]['hand_'+side], row[field]['lowerarm_'+side])
                    assert abs(length-expected) < 0.001, (frame, field, side, length)
            assert row['core_error_cm'] < 0.1, ('attack rendered mismatch', row['core_error_cm'])
        if frame >= 10 and kind != 'natural':
            if kind == 'replace' and state['phase'] == 'attack':
                event('replace', lambda: actor.call_method('TriggerNNAttack', args=(unreal.Name('slashR'), state['target'], False)))
                state['phase'] = 'replacement'; state['deadline'] = now + 20
            else:
                event('stop', lambda: actor.call_method('StopNNAttack'))
                state['phase'] = 'after'; state['deadline'] = now + 0.4
    except Exception:
        finish(traceback.format_exc())


state['handle'] = unreal.register_slate_post_tick_callback(tick)
print('Numerical full/half stop, replacement, natural completion, 60/5 FPS test started')
