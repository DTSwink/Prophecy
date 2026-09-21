import unreal,builtins,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);w=ed.get_game_world()
print('game',w)
unreal.SystemLibrary.execute_console_command(w,'HighResShot 1')
pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/SwordJump_to89.json').write_text(json.dumps(builtins._sword_jump_observation['rows']))
