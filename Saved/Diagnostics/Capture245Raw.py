import pathlib,unreal
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/Head24520261003'
(p/'mode.txt').write_text('raw_nn')
source=(p.parent/'CaptureHead505.py').read_text(encoding='utf-8-sig').replace('Diagnostics/Head50520261003','Diagnostics/Head24520261003').replace("s['frames']>=550","s['frames']>=270")
trace2=p.parent/'SlashContacts/nn_inputs.jsonl'
trace2_start=trace2.stat().st_size if trace2.exists() else 0
old_nntrace=unreal.SystemLibrary.get_console_variable_int_value('Prophecy.NNInputTraceFrames')
source=source.replace("   if mode=='core_off' and clock==504:","   if clock==230:unreal.SystemLibrary.execute_console_command(world,'Prophecy.NNInputTraceFrames 20')\n   if mode=='core_off' and clock==504:")
source=source.replace(" print('HEAD_ENTRY_DONE'", " unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.NNInputTraceFrames '+str(old_nntrace))\n if trace2.exists():\n  with trace2.open('rb') as f:f.seek(trace2_start);(p/(mode+'-inputs.jsonl')).write_bytes(f.read())\n print('HEAD_ENTRY_DONE'")
exec(compile(source,'Capture245Raw.py','exec'))
