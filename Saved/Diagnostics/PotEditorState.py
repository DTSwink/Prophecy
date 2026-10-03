import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('PLAY',bool(ed.get_game_world()))
print('DIRTY',[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()+unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])
