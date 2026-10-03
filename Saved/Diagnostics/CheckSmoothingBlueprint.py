import unreal
from pathlib import Path
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.RepairLibraryDefaults')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
p=Path(unreal.Paths.project_saved_dir())/'Diagnostics'
print((p/'LiveLibraryDefaults.txt').read_text())
print((p/'LiveAgentTypes-Inspect.txt').read_text())
