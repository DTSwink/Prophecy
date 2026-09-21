import unreal,pathlib,sys
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world,'prophecy.Jolt.WristNativeTrace 1')
sys.argv=['BoolCaptureCurrent.py', sys.argv[1] if len(sys.argv)>1 else 'true', sys.argv[2] if len(sys.argv)>2 else '10', sys.argv[3] if len(sys.argv)>3 else '35']
src=(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/WideWrist/BoolCaptureCurrent.py').read_text()
src=src.replace("print('WRIST_BOOL_DONE'", "unreal.SystemLibrary.execute_console_command(sub.get_game_world(),'prophecy.Jolt.WristNativeTrace 0')\n    print('WRIST_BOOL_DONE'")
exec(compile(src,'WristBooleanNativeCapture','exec'))
