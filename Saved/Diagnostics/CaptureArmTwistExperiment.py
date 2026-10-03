import pathlib,unreal,sys
root=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
response=float(sys.argv[2]) if len(sys.argv)>2 else 0.
no_twist=int(sys.argv[3]) if len(sys.argv)>3 else 1
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
src=(root/'CaptureWrist230.py').read_text().replace("s['frame']>=270","s['frame']>=620")
cleanup=" unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.UpperInertia.DebugResponse 0')\n unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.UpperInertia.DebugNoTwist 0')\n"
src=src.replace("exec(compile(src,'CaptureWrist230','exec'))", "src=src.replace('def finish(reason):\\n','def finish(reason):\\n'+cleanup)\nexec(compile(src,'CaptureWrist230','exec'))")
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.UpperInertia.DebugResponse '+str(response))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.UpperInertia.DebugNoTwist '+str(no_twist))
exec(compile(src,'CaptureArmTwistExperiment','exec'))
