import unreal,pathlib
src=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CaptureLeg920.py'
exec(compile(src.read_text(encoding='utf-8'),str(src),'exec'),{'__name__':'leg920_capture'})
