import unreal,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
src=(p/'CaptureSimFootFinal.py').read_text(encoding='utf-8')
src=src.replace('SimFootFinal','KneeHistoricalBaseline').replace('_sim_foot_final','_knee_historical_baseline').replace('SIM_FOOT_FINAL','KNEE_HISTORICAL_BASELINE')
src=src.replace('clock>=99999','clock>=20').replace('NNInputTraceFrames 480','NNInputTraceFrames 2200').replace('clock>=1600','clock>=950')
exec(compile(src,str(p/'CaptureSimFootFinal.py'),'exec'),{'__name__':'knee_historical_baseline'})
