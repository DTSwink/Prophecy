import unreal
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
    if hasattr(a,'get_nn_animation_layer_state'):
        print('AGENT',a.get_path_name(),'active',a.is_nn_animation_layer_active(),'state',a.get_nn_animation_layer_state())
