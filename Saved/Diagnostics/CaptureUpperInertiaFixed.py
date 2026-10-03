import pathlib,unreal
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(),'Preserve user Play'
p=pathlib.Path('C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics')
src=(p/'CaptureHand180.py').read_text().replace("tag='hand180'","tag='upper_inertia_fixed'").replace("s['frame']>=235","s['frame']>=330")
exec(compile(src,'UpperInertiaFixed','exec'))
