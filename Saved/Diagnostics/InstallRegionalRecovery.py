import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
w=ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.SplitSpecialRecovery')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RepairLibraryDefaults')
unreal.BlueprintEditorLibrary.compile_blueprint(unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent'))
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.AuditCollisionGraph')
unreal.SystemLibrary.execute_console_command(w,'Automation RunTests Prophecy.NN.SpecialRecovery+Prophecy.NN.LowerTempering+Prophecy.NN.PolicyBlend.AttackRecovery+Prophecy.NN.HandRecovery+Prophecy.NN.CoreTempering+Prophecy.NN.SlashReturn+Prophecy.NN.PhysicalTargets.AttackHandClamp')
print('REGIONAL_RECOVERY_INSTALLED_AND_TESTS_QUEUED')
