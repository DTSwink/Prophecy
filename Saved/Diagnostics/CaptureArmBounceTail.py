import pathlib,unreal,sys
root=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
src=(root/'CaptureArmBouncesTrace.py').read_text().replace("s['frame']>=620","s['frame']>=790").replace('clock>=180','clock>=710')
src=src.replace("Prophecy.ArmCone.Audit 1","Prophecy.UpperInertia.Audit 1").replace("Prophecy.ArmCone.Audit 0","Prophecy.UpperInertia.Audit 0")
exec(compile(src,'CaptureArmBounceTail','exec'))
