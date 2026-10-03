import unreal,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Tempering.HistoricalAudit 2000')
src=(p/'CaptureSimFootFinal.py').read_text(encoding='utf-8')
src=src.replace('SimFootFinal','KneeHistoricalAudit').replace('_sim_foot_final','_knee_historical_audit')
src=src.replace('clock>=99999','clock>=20').replace('NNInputTraceFrames 480','NNInputTraceFrames 1000').replace('clock>=1600','clock>=420')
src=src.replace("unreal.unregister_slate_post_tick_callback(s['cb'])","unreal.unregister_slate_post_tick_callback(s['cb'])\n unreal.SystemLibrary.execute_console_command(w0,'Prophecy.Tempering.HistoricalAudit 0')")
exec(compile(src,str(p/'CaptureSimFootFinal.py'),'exec'),{'__name__':'knee_historical_audit'})
