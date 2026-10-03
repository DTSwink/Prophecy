import unreal,pathlib,shutil,datetime
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
backup=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/MagicCubeTimeBackup'
backup.mkdir(exist_ok=True)
source=pathlib.Path(unreal.Paths.project_content_dir())/'_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset'
if not (backup/source.name).exists():shutil.copy2(source,backup/source.name)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.FixMagicCubeTime')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
print((pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')[:200])
