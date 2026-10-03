import pathlib,unreal
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
src=(p/'CaptureSupportingKneeLead.py').read_text(encoding='utf-8')
src=src.replace('SupportingKneeLead-live.json','SupportingKneeHeight-live.json').replace('_supporting_knee_lead','_supporting_knee_height')
exec(compile(src,str(p/'CaptureSupportingKneeHeight.py'),'exec'),{'__name__':'supporting_knee_height'})
