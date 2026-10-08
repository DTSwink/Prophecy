import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.AttackControls.PhaseLatches+Prophecy.NN.SpecialRecovery.RegionalOwnership+Prophecy.NN.AttackControls.EntryMagicAndTicks+Prophecy.NN.AttackControls.ManualTicks')
print('ATTACK_CONTROL_TESTS_STARTED')
