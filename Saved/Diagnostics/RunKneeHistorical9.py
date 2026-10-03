import unreal,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
src=(p/'RunKneeHistorical7.py').read_text(encoding='utf-8').replace('KneePlane 5','KneePlane 9').replace('KneeHistorical7','KneeHistorical9').replace('knee_historical7','knee_historical9')
exec(compile(src,str(p/'RunKneeHistorical7.py'),'exec'),{'__name__':'knee_historical9'})
