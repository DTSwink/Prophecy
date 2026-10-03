import unreal,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
src=(p/'RunKneeHistorical12.py').read_text(encoding='utf-8').replace('KneePlane 12','KneePlane 13').replace('KneeHistorical12','KneeHistorical13').replace('knee_historical12','knee_historical13')
exec(compile(src,str(p/'RunKneeHistorical12.py'),'exec'),{'__name__':'knee_historical13'})
