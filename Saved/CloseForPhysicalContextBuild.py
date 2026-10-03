import unreal
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
assert not list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()), 'Save edits before closing'
unreal.SystemLibrary.quit_editor()
