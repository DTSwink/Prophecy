import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
unreal.SystemLibrary.quit_editor()
