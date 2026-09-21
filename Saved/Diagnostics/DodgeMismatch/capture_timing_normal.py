import pathlib,unreal
code=(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/DodgeMismatch/capture_trace_normal.py').read_text()
exec(code.replace('trace_normal_ue.json','timing_normal_ue.json'),globals())
