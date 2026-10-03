import unreal,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
src=(p/'RunKneeHistorical20.py').read_text(encoding='utf-8').replace('KneePlane 20','KneePlane 4').replace('KneeHistorical20','KneeHistorical4').replace('knee_historical20','knee_historical4')
exec(compile(src,str(p/'RunKneeHistorical20.py'),'exec'),{'__name__':'knee_historical4'})
