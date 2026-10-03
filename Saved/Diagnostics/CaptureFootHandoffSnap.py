import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play; capture requires idle editor'
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
src=(p/'CapturePelvisHitch.py').read_text()
src=src.replace("getattr(self,'max_frames',600)","440").replace("'PelvisHitch-'","'FootHandoffSnap-'")
src=src.replace("window=unreal.ProphecyRootPhysicsLibrary", "owners=unreal.ProphecyAttackFootLocomotionLibrary.get_attack_foot_locomotion(a)\n                for bone in ('foot_l','foot_r','pelvis'):\n                    bt=a.get_authored_body_world_target(bone)\n                    if bt:bones[bone]['drive']=self.tr(bt[2])\n                window=unreal.ProphecyRootPhysicsLibrary")
src=src.replace("'frame':self.n,'tick':tick", "'owners':owners,'frame':self.n,'tick':tick")
exec(compile(src,'CaptureFootHandoffSnap','exec'))
