import unreal,pathlib,shutil
root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/SwordDraw20261010'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);assert not ed.get_game_world()
w=ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RepairLibraryDefaults')
print('REPAIR', (root/'Saved/Diagnostics/LiveLibraryDefaults.txt').read_bytes())
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.LiveAgentTypes Inspect')
print('TYPES',(root/'Saved/Diagnostics/LiveAgentTypes-Inspect.txt').read_bytes())
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.AuditCollisionGraph')
shutil.copy2(out.parent/'SwordThigh/BlueprintGraph.txt',out/'graph-wired.txt')
print('READY_FOR_COMPARE')
