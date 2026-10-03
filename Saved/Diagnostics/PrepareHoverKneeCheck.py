from pathlib import Path
p=Path('Saved/Diagnostics/CaptureHover260.py').read_text().replace('Hover260','Hover260KneeCheck').replace('hover260','hover260_kneecheck').replace('HOVER260','HOVER260_KNEECHECK').replace('n>=290','n>=266')
p=p.replace("if n>=266:finish('Complete');return", """if n>=266:
    unreal.ProphecyKneePopSmoothingLibrary.set_knee_pop_smoothing(a,False,0)
    s['rows'][-1]['without_knee_smoothing']={}
    for b in ('pelvis','thigh_l','calf_l','foot_l','ball_l'):
     target=a.get_authored_body_world_target(b)
     if target:s['rows'][-1]['without_knee_smoothing'][b]=[tr(x) for x in target[:3]]
    finish('Complete');return""")
Path('Saved/Diagnostics/CaptureHover260KneeCheck.py').write_text(p)
Path('Saved/Diagnostics/RunCaptureHover260KneeCheck.py').write_text("import pathlib,unreal\nsrc=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CaptureHover260KneeCheck.py'\nexec(compile(src.read_text(),str(src),'exec'),{'__name__':'hover260_kneecheck'})")
