import unreal,pathlib
src=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CaptureWalkKneeNow.py'
exec(compile(src.read_text(encoding='utf-8'),str(src),'exec'),{'__name__':'walk_knee_now_capture'})
