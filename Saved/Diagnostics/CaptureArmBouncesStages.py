import pathlib,unreal,sys
root=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.UpperInertia.Audit 1')
src=(root/'CaptureWrist230.py').read_text().replace("s['frame']>=270","s['frame']>=610")
src=src.replace("exec(compile(src,'CaptureWrist230','exec'))", "src=src.replace('def finish(reason):',\"def finish(reason):\\n unreal.SystemLibrary.execute_console_command(ed.get_game_world() or ed.get_editor_world(),'Prophecy.UpperInertia.Audit 0')\")\nexec(compile(src,'CaptureWrist230','exec'))")
exec(compile(src,'CaptureArmBouncesStages','exec'))
