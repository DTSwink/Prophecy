import unreal,pathlib,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.PhysicalFoot.TraceFrames 270')
src=(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CaptureWrist230.py').read_text()
src=src.replace("exec(compile(src,'CaptureWrist230','exec'))", "src=src.replace(\"def finish(reason):\", \"def finish(reason):\\n unreal.SystemLibrary.execute_console_command(ed.get_game_world() or ed.get_editor_world(),'Prophecy.PhysicalFoot.TraceFrames 0')\")\nexec(compile(src,'CaptureWrist230','exec'))")
exec(compile(src,'CaptureWrist230Ranges','exec'))
