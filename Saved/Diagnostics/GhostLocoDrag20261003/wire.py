import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.WireGhostLocoDrag')
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/GhostLocoDrag20261003'
print((p/'wiring.txt').read_text() if (p/'wiring.txt').exists() else 'NO WIRING RECEIPT')
