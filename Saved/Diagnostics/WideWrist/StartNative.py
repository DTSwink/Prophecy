import unreal, pathlib, sys
sub=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not sub.get_game_world()
unreal.SystemLibrary.execute_console_command(sub.get_editor_world(), 'prophecy.Jolt.WristNativeTrace 1')
requested=sys.argv[1] if len(sys.argv)>1 else 'current'
duration=sys.argv[2] if len(sys.argv)>2 else '30'
sys.argv=['Capture.py', requested, duration]
source=(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/WideWrist/Capture.py').read_text()
source=source.replace('if t<2:return', 'if t<0.2:return' if requested!='current' else 'if t<0:return')
source=source.replace("(mode+'.json')", "('native_'+mode+'.json')")
source=source.replace("mesh=a.get_pose_reference_mesh();lib", "print('WRIST_MAGNET',a.get_name(),{b:str(a.get_body_magnetization_settings(b)) for b in ('hand_r','lowerarm_r','upperarm_r')});mesh=a.get_pose_reference_mesh();lib")
source=source.replace("print('WIDE_WRIST_DONE'", "unreal.SystemLibrary.execute_console_command(sub.get_game_world(), 'prophecy.Jolt.WristNativeTrace 0')\n    print('WIDE_WRIST_DONE'")
exec(compile(source, 'WideWristNativeCapture', 'exec'))
