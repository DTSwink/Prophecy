import pathlib,unreal
source=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/TestSpecialRecoveryLive.py'
exec(compile(source.read_text(),str(source),'exec'),{'__name__':'special_recovery_isolated'})
