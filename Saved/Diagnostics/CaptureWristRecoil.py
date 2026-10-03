import unreal,pathlib,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
mode=sys.argv[1] if len(sys.argv)>1 else 'off'
if mode=='on':unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.PreviewArmConeTwist on')
p=pathlib.Path('C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics')
wrapper=(p/'CaptureHand180.py').read_text().replace("tag='hand180'","tag='wrist_recoil_"+mode+"'").replace("s['frame']>=235","s['frame']>=290")
exec(compile(wrapper,'CaptureWristRecoil','exec'))
