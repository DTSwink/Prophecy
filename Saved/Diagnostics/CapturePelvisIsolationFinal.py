import unreal,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics';ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Recovery.PolePresentation 1')
src=(p/'CaptureSimFootFinal.py').read_text().replace('clock>=1600','clock>=520').replace('SimFootFinal','PelvisIsolationFinal')
exec(compile(src,'CapturePelvisIsolationFinal','exec'))
