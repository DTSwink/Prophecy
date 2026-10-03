import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
assert unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySpecialRecoveryEvents')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.SpecialRecovery MoveRecovery')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.RepairLibraryDefaults')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
print('SPECIAL_RECOVERY_INSTALL_REQUESTED')
