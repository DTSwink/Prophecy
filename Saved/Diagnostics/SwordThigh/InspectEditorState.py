import unreal,json
e=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print(json.dumps(dict(pie=bool(e.get_game_world()),world=e.get_editor_world().get_path_name(),dirty=[x.get_path_name() for x in list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())])))
