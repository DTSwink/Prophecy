import unreal
from pathlib import Path
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(),'Preserve user Play'
base=Path(unreal.Paths.project_dir())/'Saved/Diagnostics'
variant=(base/'CaptureSlashReturnVariants.py').read_text()
variant=variant.replace("'SlashReturnVariants-'","'ElbowReturnCompletion-'")
variant=variant.replace('self.frame%90==0','self.frame%180==0').replace('self.frame<900','self.frame<1800').replace('self.frame>=900','self.frame>=1800')
variant=variant.replace('time.monotonic()-self.start>90','time.monotonic()-self.start>150')
weapon=(base/'CaptureSlashSword.py').read_text()
extra=weapon[weapon.index('source=source.replace("                self.rows.append(",'):weapon.rindex('exec(source,globals())')]
variant=variant.replace('exec(source,globals())',extra+'\nexec(source,globals())')
exec(variant,globals())
