import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world()
print('PIE active:', bool(w))
if w:
    for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
        print(a.get_name(), 'mode', a.get_simulation_mode(), 'attack', a.get_nn_attack_state())
