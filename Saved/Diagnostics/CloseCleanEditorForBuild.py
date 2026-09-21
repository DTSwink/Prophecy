import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Play started; preserve session.'
dirty=unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()+unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert not dirty,'Unsaved packages appeared; preserve edits: '+str([p.get_path_name() for p in dirty])
unreal.SystemLibrary.quit_editor()
