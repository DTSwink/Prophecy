import builtins,pathlib,unreal
builtins._sword_thigh_force_block=True
exec((pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CaptureSwordThigh.py').read_text())
