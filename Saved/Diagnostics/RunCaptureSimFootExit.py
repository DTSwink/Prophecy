import unreal,pathlib
src=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CaptureSimFootExit.py'
exec(compile(src.read_text(encoding='utf-8'),str(src),'exec'),{'__name__':'sim_foot_exit_capture'})
