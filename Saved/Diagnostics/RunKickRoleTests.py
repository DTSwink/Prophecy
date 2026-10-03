import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
tests=['Prophecy.NN.PolicyBlend.AttackRecovery','Prophecy.NN.PolicyBlend.RegionalPose','Prophecy.NN.LowerTempering.FootRoles','Prophecy.NN.LowerTempering.TranslationAxes','Prophecy.NN.LowerTempering.KickProfiles','Prophecy.NN.LowerTempering.ReturnTimeline','Prophecy.NN.LowerTempering.SeparateReturns','Prophecy.NN.LowerTempering.SupportSourceContracts','Prophecy.NN.LowerTempering.CalfTwistContinuity','Prophecy.NN.AgentReset.PhysicalBaseline','Prophecy.Blends.SixtyTickClock']
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests '+'+'.join(tests))
print('Queued 11 focused checks; no graph or scene changes.')
