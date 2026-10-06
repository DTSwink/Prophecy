import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/HandEntryGate20261006';p.mkdir(exist_ok=True)
w=ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.AuditCollisionGraph')
(p/'before-graph.txt').write_bytes((p.parent/'SwordThigh/BlueprintGraph.txt').read_bytes())
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RepairLibraryDefaults')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RefreshStartHandTickThreshold')
r=(p.parent/'StartHandTickThresholdPins.txt').read_text(encoding='utf-8-sig')
assert 'values_and_links_preserved=1' in r and 'status=3' in r,r
(p/'migration.txt').write_text(r)
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.AuditCollisionGraph')
(p/'after-graph.txt').write_bytes((p.parent/'SwordThigh/BlueprintGraph.txt').read_bytes())
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.LiveAgentTypes Inspect')
print(r)
unreal.SystemLibrary.execute_console_command(w,'Automation RunTests Prophecy.NN.AttackEntry.HandLifecycle+Prophecy.NN.AttackControls.EntryMagicAndTicks+Prophecy.NN.AttackControls.ManualTicks')
