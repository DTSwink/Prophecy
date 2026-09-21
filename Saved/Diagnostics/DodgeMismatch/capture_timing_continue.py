import pathlib,unreal
code=(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/DodgeMismatch/capture_trace_continue.py').read_text()
exec(code.replace('trace_continue_ue.json','timing_continue_ue.json'),globals())
