"""Short transient per-agent Blueprint API check; no asset writes or benchmark."""
import json, pathlib, traceback, unreal

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
lib = unreal.get_default_object(unreal.load_class(None, '/Script/GameAnimationSample3.ProphecyUpperRootHorizonLibrary'))
def get_horizon(agent):
    return lib.call_method('GetUpperRootRotationHorizon', args=(agent,))
def set_horizon(agent, value):
    return lib.call_method('SetUpperRootRotationHorizon', args=(agent, value))
state = dict(start=None, actors=[], phase=0)
out = pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics/UpperRootHorizonPIE.json'

def finish(result):
    unreal.unregister_slate_post_tick_callback(state['callback'])
    out.write_text(json.dumps(dict(result=result, agents=[a.get_name() for a in state['actors']]), indent=2))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('UPPER_ROOT_HORIZON_PIE', result)

def tick(_):
    try:
        world = ed.get_game_world()
        if not world:
            return
        now = unreal.GameplayStatics.get_time_seconds(world)
        if state['start'] is None:
            state['start'] = now
        if now - state['start'] < .5:
            return
        if state['phase'] == 0:
            agents = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent))
            assert len(agents) >= 2
            state['actors'] = agents
            for a in agents:
                assert get_horizon(a) == 1.0
            assert set_horizon(agents[0], .5)
            assert set_horizon(agents[1], 0)
            assert get_horizon(agents[0]) == .5
            assert get_horizon(agents[1]) == 0
            for value in [-1, 1.1, float('nan'), float('inf')]:
                assert not set_horizon(agents[0], value)
                assert get_horizon(agents[0]) == .5
            for a in agents[2:]:
                assert get_horizon(a) == 1
            state['phase'] = 1
        elif now - state['start'] >= 1.5:
            for a in state['actors']:
                assert set_horizon(a, 1)
                assert get_horizon(a) == 1
            finish('passed')
    except Exception:
        finish(traceback.format_exc())

state['callback'] = unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
