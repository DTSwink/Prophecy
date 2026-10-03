import pathlib,sys,unreal
source=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CaptureSharedCalfRecovery.py'
exec(compile(source.read_text(),str(source),'exec'),{'__name__':'calf_capture_isolated'})
