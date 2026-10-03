import pathlib,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
p=pathlib.Path('C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics')
src=(p/'CaptureHand180.py').read_text().replace("tag='hand180'","tag='arm_cone_million_before'").replace("s['frame']>=235","s['frame']>=260")
exec(compile(src,'CaptureArmConeCurrent','exec'))
