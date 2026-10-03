import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
src=(p/'CapturePelvisHitch.py').read_text()
src=src.replace("getattr(self,'max_frames',600)","500")
src=src.replace("'PelvisHitch-'","'InertiaSnap-'")
exec(compile(src,'CaptureInertiaSnap','exec'))

