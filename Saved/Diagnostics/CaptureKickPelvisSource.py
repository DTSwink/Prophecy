import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
trace=p/'SlashContacts/nn_inputs.jsonl'
offset=trace.stat().st_size if trace.exists() else 0
old=unreal.SystemLibrary.get_console_variable_int_value('Prophecy.NNInputTraceFrames')
src=(p/'CaptureKickPelvisExit.py').read_text().replace("KickPelvisExit.json","KickPelvisSource.json").replace("s['frame']>=620","s['frame']>=179")
src=src.replace("print('KICK_PELVIS_EXIT_DONE',reason,len(s['rows']))", """unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.NNInputTraceFrames '+str(old))
 if trace.exists():
  with trace.open('rb') as f:f.seek(offset);(p/'KickPelvisSource-nn.jsonl').write_bytes(f.read())
 print('KICK_PELVIS_SOURCE_DONE',reason,len(s['rows']))""")
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.NNInputTraceFrames 300')
exec(compile(src,'CaptureKickPelvisSource','exec'))
