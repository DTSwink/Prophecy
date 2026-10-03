import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None, 'User Play active; defer automation checks'
tests=[
 'Prophecy.Agent.TimeDilation.GameTickBudget',
 'Prophecy.Agent.Fists.TickTiming',
 'Prophecy.Agent.ModeTransitions.TickRetirement',
 'Prophecy.Agent.ModeTransitions.TranslationOnlyDescendants',
 'Prophecy.Blends.SixtyTickClock',
 'Prophecy.NN.LowerTempering.IndependentRecoveryClock',
 'Prophecy.NN.LowerTempering.ReconstructionFade',
 'Prophecy.NN.LowerTempering.LegCorrectionBlend',
 'Prophecy.NN.PhysicalTargets.RecoveryUpperHandoff',
 'Prophecy.NN.PhysicalTargets.RecoveryCalfLength'
]
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests '+'+'.join(tests))
print('GOLDEN_RULES_TESTS_REQUESTED',tests)
