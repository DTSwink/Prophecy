import unreal,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
src=(p/'RunKneeHistorical20.py').read_text(encoding='utf-8').replace('KneePlane 20','KneePlane 6').replace('KneeHistorical20','KneeHistorical6').replace('knee_historical20','knee_historical6')
exec(compile(src,str(p/'RunKneeHistorical20.py'),'exec'),{'__name__':'knee_historical6'})
