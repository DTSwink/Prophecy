import unreal,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
src=(p/'RunKneeHistorical11.py').read_text(encoding='utf-8').replace('KneeHistorical11','KneeHistoricalFinal').replace('knee_historical11','knee_historical_final').replace('Prophecy.Recovery.CleanSource 0','Prophecy.Recovery.CleanSource 1')
exec(compile(src,str(p/'RunKneeHistorical11.py'),'exec'),{'__name__':'knee_historical_final'})
