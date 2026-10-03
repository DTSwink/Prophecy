import unreal,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
src=(p/'CaptureSimFootFinal.py').read_text().replace('clock>=99999','clock>=330').replace('clock>=1600','clock>=440').replace('SimFootFinal','Pelvis380')
exec(compile(src,'CapturePelvis380','exec'))
