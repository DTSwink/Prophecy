import unreal, pathlib, json, time, traceback, builtins

out = pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics/PhysicalBlends/Live.json'
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world(), 'PIE must be stopped before the transient verification'
cdo = unreal.get_default_object(unreal.ProphecyAgent)
names = ['blend_body_magnetization', 'blend_body_magnetization_below',
         'blend_physical_feedback_tolerance', 'blend_physical_feedback_tolerance_below',
         'cancel_body_magnetization_blend', 'cancel_physical_feedback_tolerance_blend']
state = {'nodes': {n: hasattr(cdo, n) for n in names}, 'rows': [], 'start': None, 'last': None,
         'wall': time.perf_counter(), 'actor': None}
assert all(state['nodes'].values()), state['nodes']
builtins._physical_blend_verification = state

def finish(reason):
    unreal.unregister_slate_post_tick_callback(state['handle'])
    result = {k: v for k, v in state.items() if k not in ('actor', 'handle', 'wall')}
    result['reason'] = reason
    out.write_text(json.dumps(result, indent=2))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('PHYSICAL_BLEND_LIVE_DONE', reason)

def tick(dt):
    try:
        if time.perf_counter() - state['wall'] > 90:
            finish('Timeout')
            return
        world = editor.get_game_world()
        if not world:
            return
        t = unreal.GameplayStatics.get_time_seconds(world)
        if t == state['last'] or t < 2:
            return
        state['last'] = t
        if state['actor'] is None:
            agents = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent))
            agents = [a for a in agents if a.is_jolt_physical_animation_enabled()]
            assert agents, 'Current scene has no active Jolt character'
            actor = next((a for a in agents if isinstance(a.get_controller(), unreal.PlayerController)), agents[0])
            state['actor'] = actor
            state['actor_name'] = actor.get_name()
            state['jolt'] = actor.is_jolt_physical_animation_enabled()
            actor.set_body_magnetization('head', True, 0.0, 0.0)
            actor.set_physical_feedback_tolerance('head', 0.0, 0.0)
            assert actor.blend_body_magnetization('head', 1.0, 1.0, 1.0)
            assert actor.blend_physical_feedback_tolerance('head', 3.0, 5.0, 1.0)
            state['start'] = t
        actor = state['actor']
        strength = actor.get_body_magnetization_settings('head')
        feedback = actor.get_physical_feedback_tolerance('head')
        elapsed = t - state['start']
        x = min(1.0, max(0.0, elapsed))
        expected = x*x*(3 - 2*x)
        row = {'elapsed': elapsed, 'linear_strength': strength.linear_strength_scale,
               'angular_strength': strength.angular_strength_scale,
               'linear_feedback': feedback.linear_tolerance_cm,
               'angular_feedback': feedback.angular_tolerance_degrees,
               'expected_alpha': expected}
        state['rows'].append(row)
        assert abs(row['linear_strength'] - expected) < 0.0001, row
        assert abs(row['angular_strength'] - expected) < 0.0001, row
        assert abs(row['linear_feedback'] - 3*expected) < 0.0003, row
        assert abs(row['angular_feedback'] - 5*expected) < 0.0005, row
        if elapsed >= 1.2:
            assert row['linear_strength'] == 1.0 and row['angular_feedback'] == 5.0
            finish('Passed')
    except Exception:
        finish(traceback.format_exc())

state['handle'] = unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('PHYSICAL_BLEND_LIVE_STARTED')
