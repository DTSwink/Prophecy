import unreal,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Tempering.KneePlane 20')
src=(p/'RunKneeHistoricalBaseline.py').read_text(encoding='utf-8')
src=src.replace('KneeHistoricalBaseline','KneeHistorical20').replace('_knee_historical_baseline','_knee_historical20')
src=src.replace("exec(compile(src,", "src=src.replace(\"unreal.unregister_slate_post_tick_callback(s['cb'])\",\"unreal.unregister_slate_post_tick_callback(s['cb'])\\n unreal.SystemLibrary.execute_console_command(w0,'Prophecy.Tempering.KneePlane 3')\")\nexec(compile(src,")
exec(compile(src,str(p/'RunKneeHistoricalBaseline.py'),'exec'),{'__name__':'knee_historical20'})
