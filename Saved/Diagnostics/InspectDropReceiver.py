import unreal,json
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if w:
    a=unreal.GameplayStatics.get_player_pawn(w,0)
    if a:
        sword=a.get_held_sword()
        print('HELD',sword)
        if sword:
            print('RECEIVERS',[(c.get_name(),c.get_class().get_name()) for c in sword.get_components_by_class(unreal.StaticMeshComponent)])
            print('CONTROLLER', [(c.get_name(),str(c.get_editor_property('jolt_body'))) for c in a.get_components_by_class(unreal.ProphecySwordComponent)])
