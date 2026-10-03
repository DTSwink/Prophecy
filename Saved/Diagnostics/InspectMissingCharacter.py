import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('PLAY_ACTIVE',bool(ed.get_game_world()))
for w in [ed.get_editor_world(),ed.get_game_world()]:
    if not w:continue
    print('WORLD',w.get_path_name())
    for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor):
        name=a.get_class().get_path_name()
        if '/Script/Engine.StaticMeshActor' not in name:
            print('ACTOR',a.get_name(),a.get_actor_label(),name,str(a.get_actor_location()))
    ws=w.get_world_settings()
    print('GAME_MODE',ws.get_editor_property('default_game_mode'))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
