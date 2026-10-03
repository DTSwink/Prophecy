import unreal,pathlib
src=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CaptureKnee1089Fixed.py'
exec(compile(src.read_text(encoding='utf-8'),str(src),'exec'),{'__name__':'knee1089_fixed_capture'})
