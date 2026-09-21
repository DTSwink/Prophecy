import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('EditorWorld',ed.get_editor_world().get_path_name(),'PIE',bool(ed.get_game_world()))
print('DirtyMaps',[p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if 'cube' not in (a.get_actor_label()+a.get_name()).lower():continue
    for m in a.get_components_by_class(unreal.StaticMeshComponent):
        print('Cube',a.get_actor_label(),m.get_path_name(),'asset',m.static_mesh,'mobility',m.mobility,'collision',m.get_collision_enabled(),'profile',m.get_collision_profile_name(),'simulate',m.is_simulating_physics(),'position',m.get_world_location(),'scale',m.get_world_scale())
if ed.get_game_world():unreal.SystemLibrary.execute_console_command(ed.get_game_world(),'Prophecy.Jolt.MeshAudit')
