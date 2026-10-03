import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
w=ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RefreshAttackTargetExtraReach')
report=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/AttackTargetExtraReachPins.txt').read_text(encoding='utf-8-sig')
assert 'values_and_links_preserved=1' in report,report
print('REACH_UPGRADE',report)
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RepairLibraryDefaults')
report=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/LiveLibraryDefaults.txt').read_text(encoding='utf-8-sig')
assert 'status=3 ' in report and 'other_values_and_wiring_preserved=1' in report,report
print('BLUEPRINT',report)
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.AuditCollisionGraph')
unreal.SystemLibrary.execute_console_command(w,'Automation RunTests Prophecy.Attack.TargetReach')
