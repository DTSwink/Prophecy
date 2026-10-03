import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
world=ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(world,'Prophecy.Editor.LiveAgentTypes Repair')
unreal.SystemLibrary.execute_console_command(world,'Prophecy.Editor.RepairLibraryDefaults')
report=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/LiveLibraryDefaults.txt').read_text(encoding='utf-8-sig')
print(report)
assert 'status=3 ' in report and 'other_values_and_wiring_preserved=1' in report,report
unreal.SystemLibrary.execute_console_command(world,'Automation RunTests Prophecy.Jolt.Sword.AttackCollisionPhases')
