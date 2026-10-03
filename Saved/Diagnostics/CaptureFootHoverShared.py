import pathlib,unreal
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
src=(p/'CaptureFootHover.py').read_text(encoding='utf-8')
src=src.replace('FootHoverCurrent','FootHoverShared').replace('>=600','>=300')
src=src.replace("assert not ed.get_game_world(),'Preserve active user Play'",'')
exec(compile(src,str(p/'CaptureFootHoverShared.py'),'exec'),{'__name__':'foot_hover_shared'})
