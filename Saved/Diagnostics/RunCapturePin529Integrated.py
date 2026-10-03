import pathlib,unreal
src=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CapturePin529Integrated.py'
exec(compile(src.read_text(),str(src),'exec'),{'__name__':'pin529_integrated'})
