import unreal,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'User Play is active; do not replace it'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Tempering.PoleTrace 1200')
(p/'RecoveryPoleSmoothing.jsonl').write_text('')
src=(p/'CaptureSupportingKneeLead.py').read_text().replace('SupportingKneeLead-live','Leg190-live').replace('>=360','>=300')
src=src.replace("print('SUPPORTING_KNEE_CAPTURE_DONE',reason,len(s['rows']))", "print('SUPPORTING_KNEE_CAPTURE_DONE',reason,len(s['rows']))\n unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Tempering.PoleTrace 0')\n (pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/Leg190-frozen.jsonl').write_text((pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RecoveryPoleSmoothing.jsonl').read_text())")
exec(compile(src,'CaptureLeg190','exec'))
