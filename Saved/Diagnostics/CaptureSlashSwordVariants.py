import unreal
from pathlib import Path
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
base=Path(unreal.Paths.project_dir())/'Saved/Diagnostics'
variant=(base/'CaptureSlashReturnVariants.py').read_text()
weapon=(base/'CaptureSlashSword.py').read_text()
start=weapon.index('source=source.replace("                self.rows.append(")') if False else weapon.index('source=source.replace("                self.rows.append(",')
extra=weapon[start:weapon.rindex('exec(source,globals())')]
variant=variant.replace("'SlashReturnVariants-'","'SlashSwordVariants-'")
variant=variant.replace('exec(source,globals())',extra+'\nexec(source,globals())')
exec(variant,globals())
