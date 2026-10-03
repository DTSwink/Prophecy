import unreal,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
src=(p/'RunKneeHistorical7.py').read_text(encoding='utf-8').replace('KneePlane 5','KneePlane 8').replace('KneeHistorical7','KneeHistorical8').replace('knee_historical7','knee_historical8')
exec(compile(src,str(p/'RunKneeHistorical7.py'),'exec'),{'__name__':'knee_historical8'})
