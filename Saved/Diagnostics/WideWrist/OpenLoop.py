import unreal,pathlib,sys
sub=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not sub.get_game_world()
requested=sys.argv[1]
sys.argv=['Capture.py',requested,'30']
source=(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/WideWrist/Capture.py').read_text()
source=source.replace('if t<2:return','if t<0.2:return')
source=source.replace("(mode+'.json')", "('openloop_'+mode+'.json')")
source=source.replace("if mode=='free':", "print('WRIST_OPENLOOP',a.get_name(),a.set_all_physical_feedback_tolerances(1000000,360))\n                if mode=='free':")
exec(compile(source,'WideWristOpenLoop','exec'))
