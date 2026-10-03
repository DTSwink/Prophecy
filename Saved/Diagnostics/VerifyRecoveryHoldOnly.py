import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.PolicyBlend.AttackRecovery+Prophecy.NN.PolicyBlend.RecoveryHoldOnly+Prophecy.NN.PolicyBlend.RecoveryFootRotation+Prophecy.NN.SpecialRecovery.AllExitsAndRetirement+Prophecy.Blends.SixtyTickClock')
