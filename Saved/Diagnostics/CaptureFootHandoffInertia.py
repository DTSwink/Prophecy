import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
src=(p/'CaptureFootHandoffSnap.py').read_text()
src=src.replace("exec(compile(src,'CaptureFootHandoffSnap','exec'))", "src=src.replace(\"'FootHandoffSnap-'\",\"'FootHandoffInertia-'\")\nsrc=src.replace(\"mesh=a.get_pose_reference_mesh();pose=a.read_nn_future_world_pose()\",\"unreal.ProphecyAttackStartInertiaLibrary.set_attack_start_foot_inertia(a,True,10,1.,10,1.)\\n                mesh=a.get_pose_reference_mesh();pose=a.read_nn_future_world_pose()\")\nexec(compile(src,'CaptureFootHandoffInertia','exec'))")
exec(compile(src,'CaptureFootHandoffInertiaWrapper','exec'))
