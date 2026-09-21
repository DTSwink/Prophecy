import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'PIE is running; leave it alone.'
print('Dirty assets', [x.get_path_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()])
print('Dirty maps', [x.get_path_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'LiveCoding.Compile')
print('Requested live compile; no editor restart.')
