import unreal,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
src=(p/'VerifyRecoveryIsolation.py').read_text().replace('PolePresentation 1','PolePresentation 0')
exec(compile(src,'VerifyRecoveryIsolationLegacy','exec'))
