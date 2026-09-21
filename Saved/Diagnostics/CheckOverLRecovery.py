import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Preserving active Play'
tests=[
 'Prophecy.NN.LowerTempering.CalfTwistContinuity',
 'Prophecy.NN.LowerTempering.StancePlaneIdentity',
 'Prophecy.NN.LowerTempering.StancePlaneConnectedRegression',
 'Prophecy.NN.LowerTempering.StancePlaneRaisedSource',
 'Prophecy.NN.LowerTempering.StancePlaneDegeneracy',
 'Prophecy.NN.LowerTempering.RootLocalPinAndChain',
 'Prophecy.NN.LowerTempering.SupportSourceContracts',
 'Prophecy.NN.LowerTempering.TranslationAxes',
 'Prophecy.NN.PolicyBlend.AttackRecovery',
 'Prophecy.NN.PolicyBlend.RegionalPose',
 'Prophecy.NN.PhysicalTargets.KickLeewayInheritance',
 'Prophecy.Joints.KickFootLeeway',
]
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests '+'+'.join(tests))
print('Requested',len(tests),'focused recovery checks')
