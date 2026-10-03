import unreal,builtins,gc,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve active Play'
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/FootVibration-final-verification.json'
assert p.exists()
s=getattr(builtins,'_calf_connection',None)
if isinstance(s,dict):
 print('RELEASED_COMPLETED_FOOT_CAPTURE',len(s.get('rows',[])))
 s.get('rows',[]).clear()
gc.collect()
print('FOOT_VIBRATION_CAPTURE_RELEASED',ed.get_editor_world().get_path_name())
