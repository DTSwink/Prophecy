import pathlib,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
p=pathlib.Path('C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics')
src=(p/'CaptureHand180.py').read_text().replace("tag='hand180'","tag='arm_cone_nn_audit'").replace("s['frame']>=235","s['frame']>=220")
src=src.replace("exec(compile(src,'CaptureHand180','exec'))","src=src.replace(\" unreal.unregister_slate_post_tick_callback(s['cb'])\",\" unreal.unregister_slate_post_tick_callback(s['cb'])\\n unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.ArmCone.Audit 0')\")\nexec(compile(src,'CaptureHand180','exec'))")
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.ArmCone.Audit 1')
exec(compile(src,'CaptureArmConeNNAudit','exec'))
