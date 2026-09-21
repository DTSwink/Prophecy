import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'User PIE is running'
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), 'Unsaved assets'
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), 'Unsaved map'
w=ed.get_editor_world()
(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/DodgeMismatch/restart_state.json').write_text(json.dumps({'map':w.get_path_name()}))
unreal.SystemLibrary.execute_console_command(w,'QUIT_EDITOR')
