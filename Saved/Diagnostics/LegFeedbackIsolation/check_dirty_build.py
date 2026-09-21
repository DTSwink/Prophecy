import unreal,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print(json.dumps({'pie':bool(ed.get_game_world()),'dirty_maps':[x.get_path_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],'dirty_content':[x.get_path_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]}))
