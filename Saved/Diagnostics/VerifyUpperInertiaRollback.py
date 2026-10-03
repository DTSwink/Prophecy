import pathlib
import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user Play'
w=ed.get_editor_world()
saved=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.AuditCollisionGraph')
before=(saved/'SwordThigh/BlueprintGraph.txt').read_bytes()
(saved/'UpperCoreArms-20261002-comparison/graph-before-rollback-refresh.txt').write_bytes(before)
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RefreshUpperInertiaSpace')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RepairLibraryDefaults')
data=(saved/'LiveLibraryDefaults.txt').read_bytes()
report=data.decode('utf-16' if data.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig')
print('ROLLBACK_BLUEPRINT',report)
assert 'status=3' in report or 'status=5' in report,report
assert 'other_values_and_wiring_preserved=1' in report,report
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.AuditCollisionGraph')
print('UPPER_INERTIA_SHARED_CODE_READY_FOR_USER_COMPARISON')
