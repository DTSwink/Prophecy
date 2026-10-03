import pathlib,unreal,sys
root=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
src=(root/'CaptureWrist230.py').read_text().replace("s['frame']>=270","s['frame']>=760")
exec(compile(src,'CaptureArmBounces','exec'))
