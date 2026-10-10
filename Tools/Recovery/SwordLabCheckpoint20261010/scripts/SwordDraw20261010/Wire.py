import unreal,pathlib,shutil
root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/SwordDraw20261010'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
w=ed.get_editor_world()
print('LIBRARY',getattr(unreal,'ProphecySwordHolsterLibrary',None))
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.LiveAgentTypes Inspect')
print((root/'Saved/Diagnostics/LiveAgentTypes-Inspect.txt').read_bytes()[:1000])
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RepairLibraryDefaults')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.AuditCollisionGraph')
shutil.copy2(out.parent/'SwordThigh/BlueprintGraph.txt',out/'graph-reload.txt')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.WireSwordHolster')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.AuditCollisionGraph')
shutil.copy2(out.parent/'SwordThigh/BlueprintGraph.txt',out/'graph-wired.txt')
print('WIRING', (out/'wiring.txt').read_bytes())

