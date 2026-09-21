import pathlib
import time
import traceback
import unreal

# Reuse the original diagnosis sampler without changing its historical behavior.
root = pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics' / 'PelvisBackward'
scope = {'__name__': '__pelvis_fix_validation__'}
exec(compile((root / 'capture_live.py').read_text(encoding='utf-8'), str(root / 'capture_live.py'), 'exec'), scope)
state = scope['state']
unreal.unregister_slate_post_tick_callback(state['handle'])
state['handle'] = None
state['duration'] = 50.0
state['path'] = str(root / ('fixed-capture-' + time.strftime('%H%M%S') + '.json'))
state['injections'] = []
state['validation_settings'] = None
original_tick = scope['tick']

def tick(dt):
    try:
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        if world:
            now = float(unreal.GameplayStatics.get_time_seconds(world))
            agent = unreal.GameplayStatics.get_player_pawn(world, 0)
            if (state['validation_settings'] is None and now >= 2.0
                    and isinstance(agent, unreal.ProphecyAgent)
                    and agent.is_jolt_physical_animation_enabled()):
                agent.set_all_physical_feedback_tolerances(0.0, 0.0)
                result = agent.set_jolt_self_collision_enabled(False)
                if agent.get_held_sword():
                    agent.drop_sword()
                agent.set_locomotion_input(unreal.Vector(1, 0, 0), False, unreal.Vector(0, -1, 0), 1.0, 1.0)
                state['validation_settings'] = {
                    't': now, 'feedback_all': str(agent.get_editor_property('physical_feedback_tolerances')),
                    'self_collision_result': str(result),
                    'self_collision_pair': str(agent.get_jolt_body_pair_self_collision_enabled('hand_l', 'head')),
                    'sword': str(agent.get_held_sword()),
                    'input': str(agent.get_editor_property('locomotion_input'))}
        original_tick(dt)
        if state['done']:
            return
        if state['validation_settings'] and len(state['injections']) < 18:
            now = state['last_time']
            index = len(state['injections'])
            if now >= 5.0 + 1.3 * index:
                delay = (0.035, 0.043, 0.052)[index % 3]
                before = time.perf_counter()
                time.sleep(delay)
                state['injections'].append({'after_world_time': now, 'requested_seconds': delay,
                                            'actual_seconds': time.perf_counter() - before})
    except Exception:
        state['error'] = traceback.format_exc()
        scope['finish']('Validation error')

state['handle'] = unreal.register_slate_post_tick_callback(tick)
print('FIX_VALIDATION_STARTED', state['path'])
