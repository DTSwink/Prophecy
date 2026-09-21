import builtins
import json
import pathlib
import time
import traceback
import unreal

KEY = '_prophecy_pelvis_backward_capture'
old = getattr(builtins, KEY, None)
if old and old.get('handle'):
    raise RuntimeError('A pelvis capture is already running')
output = pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics' / 'PelvisBackward'
output.mkdir(parents=True, exist_ok=True)
state = {'handle': None, 'rows': [], 'metadata': {}, 'started_wall': time.perf_counter(),
         'last_time': None, 'first_time': None, 'path': str(output / ('capture-' + time.strftime('%H%M%S') + '.json')),
         'duration': 75.0, 'done': False, 'error': None, 'actor': None, 'mesh': None}
setattr(builtins, KEY, state)

def vec(v):
    return [float(v.x), float(v.y), float(v.z)]

def finish(reason):
    if state['handle']:
        unreal.unregister_slate_post_tick_callback(state['handle'])
        state['handle'] = None
    state['done'] = True
    state['reason'] = reason
    payload = {k: v for k, v in state.items() if k not in ('actor', 'mesh', 'handle', 'finish')}
    pathlib.Path(state['path']).write_text(json.dumps(payload, separators=(',', ':')), encoding='utf-8')
    print('PELVIS_CAPTURE_DONE', reason, len(state['rows']), state['path'])

state['finish'] = finish

def tick(slate_dt):
    try:
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        if not world:
            if state['actor']:
                finish('PIE ended')
            elif time.perf_counter() - state['started_wall'] > 30:
                finish('No PIE world')
            return
        now = float(unreal.GameplayStatics.get_time_seconds(world))
        if now == state['last_time']:
            return
        if state['actor'] is None:
            agent = unreal.GameplayStatics.get_player_pawn(world, 0)
            if not isinstance(agent, unreal.ProphecyAgent) or not agent.is_jolt_physical_animation_enabled():
                return
            components = {c.get_name(): c for c in agent.get_components_by_class(unreal.ActorComponent)}
            state['actor'] = agent
            state['mesh'] = components['PhysicalMesh']
            state['first_time'] = now
            state['metadata'] = {'actor': agent.get_path_name(), 'label': agent.get_actor_label(),
                'components': list(components), 'feedback_pelvis': str(agent.get_physical_feedback_tolerance('pelvis')),
                'feedback_all': str(agent.get_editor_property('physical_feedback_tolerances')),
                'magnetization': str(agent.get_editor_property('body_magnetization_settings')),
                'self_collision_hand_head': str(agent.get_jolt_body_pair_self_collision_enabled('hand_l','head')),
                'locomotion_input': str(agent.get_editor_property('locomotion_input')),
                'sword': str(agent.get_held_sword()), 'jolt': True,
                'sampling': 'Slate post tick; deduplicated world time; no state setters or forced evaluation'}
        agent = state['actor']
        pose = agent.read_nn_future_world_pose()
        body = agent.get_physical_body_state('pelvis')
        locomotion = agent.get_locomotion_state()
        if pose and body and locomotion:
            names, future, presented, alpha = pose
            i = next(i for i, n in enumerate(names) if str(n) == 'pelvis')
            row = {'t': now, 'dt': float(unreal.GameplayStatics.get_world_delta_seconds(world)),
                'slate_dt': float(slate_dt), 'alpha': float(alpha),
                'capsule': vec(agent.get_actor_location()), 'mover_v': vec(locomotion[0]),
                'facing': vec(locomotion[1]), 'run': bool(locomotion[2]),
                'future': vec(future[i].translation), 'target': vec(presented[i].translation),
                'body': vec(body[0].translation), 'body_v': vec(body[1]),
                'visible': vec(state['mesh'].get_socket_location('pelvis')),
                'mesh_origin': vec(state['mesh'].get_world_location())}
            state['rows'].append(row)
        state['last_time'] = now
        if now - state['first_time'] >= state['duration'] or len(state['rows']) >= 15000:
            finish('Duration complete')
    except Exception:
        state['error'] = traceback.format_exc()
        finish('Capture error')

state['handle'] = unreal.register_slate_post_tick_callback(tick)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if not world:
    editor_world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if '/Game/testNN.' not in editor_world.get_path_name():
        finish('Unexpected editor map')
        raise RuntimeError('Expected testNN')
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('PELVIS_CAPTURE_STARTED', state['path'])
