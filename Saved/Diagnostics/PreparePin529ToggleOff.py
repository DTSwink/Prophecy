from pathlib import Path
s=Path('Saved/Diagnostics/CapturePin529Integrated.py').read_text().replace('Pin529Integrated','Pin529ToggleOff').replace('pin529_integrated','pin529_toggleoff').replace('PIN529_INTEGRATED','PIN529_TOGGLEOFF').replace('n>=536','n>=528').replace('n>=550','n>=530')
s=s.replace("s['disabled']=True", """s['disabled']=True
    target=a.get_authored_body_world_target('foot_l')
    s['rows'][-1]['after_disable']=[tr(x) for x in target[:3]]""")
Path('Saved/Diagnostics/CapturePin529ToggleOff.py').write_text(s)
Path('Saved/Diagnostics/RunCapturePin529ToggleOff.py').write_text("import pathlib,unreal\nsrc=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CapturePin529ToggleOff.py'\nexec(compile(src.read_text(),str(src),'exec'),{'__name__':'pin529_toggleoff'})")
