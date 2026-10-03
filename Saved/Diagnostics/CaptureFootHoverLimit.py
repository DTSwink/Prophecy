import pathlib,unreal
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
src=(p/'CaptureFootHover.py').read_text(encoding='utf-8')
src=src.replace('FootHoverCurrent','FootHoverLimit').replace('>=600','>=260')
src=src.replace("src=src.replace(\"s['rows'].append(r)\",", "src=src.replace(\"s['rows'].append(r)\",\"if r['tick']==216:unreal.ProphecyKickFootLeewayLibrary.set_kick_foot_joint_leeway(a,8.0,1.0)\\n   \"+")
exec(compile(src,str(p/'CaptureFootHoverLimit.py'),'exec'),{'__name__':'foot_hover_limit'})
