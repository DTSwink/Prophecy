"""Short PIE-only root-yaw handoff check on the non-player agent. No asset saves."""
import json
import math
import time
import traceback
from pathlib import Path
import unreal

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_game_world() or unreal.EditorLevelLibrary.get_game_world()
assert world, 'PIE must be running'
agents = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
actor = next(a for a in agents if a.get_agent_handle().index == 1)
saved_mode = actor.get_simulation_mode()
saved_tick = actor.is_actor_tick_enabled()
assert actor.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
actor.set_actor_tick_enabled(False)
mesh = actor.get_pose_reference_mesh()
manager = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyNNLocomotionManager)[0]
saved_debug = actor.get_editor_property('show_kinematic_debug_mesh')
saved_fps = unreal.SystemLibrary.get_console_variable_float_value('t.MaxFPS')
actor.set_show_kinematic_debug_mesh(True)
yaw_audit = {'handle': None, 'rows': [], 'deadline': time.monotonic()+20, 'case': 0}
cases = [(60, 'stop', -165), (60, 'replace', 20), (5, 'stop', 140), (5, 'replace', -70)]


def xyz(v):
    return [v.x, v.y, v.z]


def quat(q):
    return [q.x, q.y, q.z, q.w]


def transform(t):
    return {'p': xyz(t.translation), 'q': quat(t.rotation), 's': xyz(t.scale3d)}


def snapshot():
    names, future, presented, _ = actor.read_nn_future_world_pose()
    debug = unreal.find_object(manager, 'KinematicDebugMesh_1')
    return {'root': xyz(actor.get_root_low_point()),
            'facing': xyz(actor.get_locomotion_state()[1]),
            'target_facing': xyz(actor.call_method('GetLocomotionTarget')[2]),
            'future': {str(n): transform(t) for n, t in zip(names, future)},
            'presented': {str(n): transform(t) for n, t in zip(names, presented)},
            'mesh': {str(n): transform(mesh.get_socket_transform(n, unreal.RelativeTransformSpace.RTS_WORLD)) for n in names},
            'debug': {str(n): transform(debug.get_socket_transform(n, unreal.RelativeTransformSpace.RTS_WORLD)) for n in names} if debug else {}}


def finish(error=None):
    if yaw_audit['handle'] is not None:
        unreal.unregister_slate_post_tick_callback(yaw_audit['handle'])
        yaw_audit['handle'] = None
    actor.set_show_kinematic_debug_mesh(saved_debug)
    actor.set_simulation_mode(saved_mode)
    actor.set_actor_tick_enabled(saved_tick)
    unreal.SystemLibrary.execute_console_command(world, f't.MaxFPS {saved_fps}')
    output = Path(unreal.Paths.project_saved_dir()).resolve() / 'SlashParity/attack_root_yaw.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'passed': error is None, 'error': error, 'rows': yaw_audit['rows']}, indent=2))
    print('Attack root yaw audit:', output, 'error=', error)


def sample(_dt):
    try:
        index = yaw_audit['case']
        if index == len(cases):
            finish(); return
        assert time.monotonic() < yaw_audit['deadline'], 'No suitable attack observed'
        fps, kind, heading = cases[index]
        if yaw_audit.get('started') != index:
            unreal.SystemLibrary.execute_console_command(world, f't.MaxFPS {fps}')
            # This NPC may also have a Blueprint attack loop. Its actual family
            # is deliberately not assumed; the check controls only the handoff target.
            target = actor.get_actor_transform().transform_location(unreal.Vector(-40, 120, 0))
            assert actor.call_method('TriggerNNAttack', args=(unreal.Name('slashL'), target, False))
            yaw_audit['started'] = index
            return
        attack = actor.call_method('GetNNAttackState')
        if not attack or attack[1] or attack[-1] < 5: return
        before = snapshot()
        direction = [math.sin(math.radians(heading)), math.cos(math.radians(heading)), 0]
        pelvis = before['future']['pelvis']['p']
        target = unreal.Vector(*(p+150*d for p, d in zip(pelvis, direction)))
        assert actor.call_method('SetNNAttackTarget', args=(target,))
        if kind == 'stop':
            assert actor.call_method('StopNNAttack')
        else:
            assert actor.call_method('TriggerNNAttack', args=(unreal.Name('slashR'), target, False))
        after = snapshot()
        row = {'fps': fps, 'event': kind, 'attack': str(attack), 'heading_degrees': heading,
               'root_shift_cm': math.dist(before['root'], after['root']),
               'facing_error': math.dist(direction, after['facing']),
               'target_facing_error': math.dist(direction, after['target_facing']), 'checks': {}}
        for channel in ['future', 'presented', 'mesh', 'debug']:
            a, b = before[channel], after[channel]
            if not a: continue
            max_position = max(math.dist(a[n]['p'], b[n]['p']) for n in a)
            # Quaternion sign is not orientation; q and -q encode the same rotation.
            max_rotation = max(min(math.dist(a[n]['q'], b[n]['q']),
                                   math.dist(a[n]['q'], [-v for v in b[n]['q']])) for n in a)
            row['checks'][channel] = {'position_jump_cm': max_position, 'quaternion_jump': max_rotation}
        row['calf_scale_error'] = max(abs(v-1) for bone in ['calf_l', 'calf_r']
                                      for v in after['mesh'][bone]['s'])
        yaw_audit['rows'].append(row)
        # GetLocomotionTarget is explicitly the last consumed mover goal, so it
        # updates on the next 30 Hz step, not inside this synchronous handoff.
        assert row['facing_error'] < 1e-6, row
        assert row['calf_scale_error'] < 1e-5, row
        for result in row['checks'].values():
            assert result['position_jump_cm'] < 1e-5 and result['quaternion_jump'] < 1e-6, row
        yaw_audit['case'] += 1
        yaw_audit['deadline'] = time.monotonic()+20
    except Exception:
        finish(traceback.format_exc())


yaw_audit['handle'] = unreal.register_slate_post_tick_callback(sample)
print('Root yaw / world-pose continuity / calf scale test started on NPC lane 1')
