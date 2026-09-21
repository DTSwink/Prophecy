import pathlib,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Debug.DodgeTrace 1')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Debug.DodgeContinueAfterContact 0')
code=(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/capture_current_dodge_mismatch.py').read_text()
code=code.replace("'corrected_ue.json'","'trace_normal_ue.json'")
code=code.replace("print('DODGE_MISMATCH_CAPTURE'", "unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Debug.DodgeTrace 0')\n print('DODGE_MISMATCH_CAPTURE'")
exec(code,globals())
