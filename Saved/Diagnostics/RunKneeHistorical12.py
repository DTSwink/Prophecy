import unreal,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
src=(p/'RunKneeHistorical11.py').read_text(encoding='utf-8').replace("'Prophecy.Tempering.KneePlane 3'","'Prophecy.Tempering.KneePlane 12'").replace('KneeHistorical11','KneeHistorical12').replace('knee_historical11','knee_historical12')
src=src.replace("unreal.SystemLibrary.execute_console_command(w0,'Prophecy.Recovery.CleanSource 0')", "unreal.SystemLibrary.execute_console_command(w0,'Prophecy.Recovery.CleanSource 0');unreal.SystemLibrary.execute_console_command(w0,'Prophecy.Tempering.KneePlane 3')")
exec(compile(src,str(p/'RunKneeHistorical11.py'),'exec'),{'__name__':'knee_historical12'})
