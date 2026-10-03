import pathlib,unreal
src=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CaptureHover260KneeCheck.py'
exec(compile(src.read_text(),str(src),'exec'),{'__name__':'hover260_kneecheck'})