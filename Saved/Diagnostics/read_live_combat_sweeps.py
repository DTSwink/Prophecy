import unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w = ed.get_game_world()
lib = unreal.get_default_object(unreal.load_class(None, '/Script/ProphecyJolt.ProphecyJoltPHATSweepLibrary'))
if w:
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.ProphecyAgent):
        print('SWEEP_LIVE', a.get_name(), unreal.ProphecyNNDefenseLibrary.get_agent_state(a), lib.call_method('GetJoltPHATSweeps', (a,)))
else:
    print('SWEEP_LIVE_NO_PIE')
