import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_editor_world()
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/LegFeedbackIsolation/editor_reopen.json'
p.write_text(json.dumps({'map':w.get_outermost().get_name()}))
assert not ed.get_game_world()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
unreal.SystemLibrary.execute_console_command(w,'t.MaxFPS 60')
print('CLOSING_SAVED_EDITOR',w.get_path_name())
unreal.SystemLibrary.execute_console_command(w,'QUIT_EDITOR')
