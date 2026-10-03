import unreal,pathlib,sys
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(),'Preserve user Play'
root=pathlib.Path('C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics')
tag=sys.argv[1] if len(sys.argv)>1 else 'wrist230_before'
src=(root/'CaptureKnee202.py').read_text().replace('clock>=175','clock>=999999').replace("s['frame']>=280","s['frame']>=270")
src=src.replace("tag=sys.argv[1] if len(sys.argv)>1 else 'baseline'","tag="+repr(tag))
src=src.replace("bones=('pelvis','thigh_l','calf_l','foot_l','ball_l','thigh_r','calf_r','foot_r','ball_r')","bones=('pelvis','spine_05','clavicle_l','upperarm_l','lowerarm_l','hand_l','clavicle_r','upperarm_r','lowerarm_r','hand_r','thigh_l','calf_l','foot_l','thigh_r','calf_r','foot_r')")
unreal.SystemLibrary.execute_console_command(unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
exec(compile(src,'CaptureWrist230','exec'))
