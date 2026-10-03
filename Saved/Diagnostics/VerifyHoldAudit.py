import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
tests=['Prophecy.NN.HandRecovery.ControlsAndLifecycle','Prophecy.NN.CoreTempering.Lifecycle',
 'Prophecy.NN.LowerTempering.ReturnTimeline','Prophecy.NN.LowerTempering.SeparateReturns',
 'Prophecy.NN.LowerTempering.KickProfiles','Prophecy.NN.LowerTempering.FootRoles',
 'Prophecy.NN.PolicyBlend.AttackRecovery','Prophecy.NN.PolicyBlend.RecoveryHoldOnly',
 'Prophecy.NN.PolicyBlend.RecoveryFootRotation','Prophecy.Root.KickSelfBalancingException',
 'Prophecy.NN.SlashReturn.RouteAndLifecycle','Prophecy.NN.UpperBodyInertia.SpringAndRetirement',
 'Prophecy.NN.SpecialRecovery.AllExitsAndRetirement','Prophecy.Blends.SixtyTickClock']
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests '+'+'.join(tests))
