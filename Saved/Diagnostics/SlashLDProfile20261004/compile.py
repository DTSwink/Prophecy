import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world()
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SlashLDProfile20261004'
(p/'editor-before.json').write_text(json.dumps({'play':w is not None,'paused':unreal.GameplayStatics.is_game_paused(w) if w else False,'dirty':[x.get_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]}))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'LiveCoding.Compile')
print('Profile-only Live Coding requested; current Play untouched')
