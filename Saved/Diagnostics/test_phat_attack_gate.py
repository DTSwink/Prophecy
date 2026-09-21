import unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('SWEEP_ATTACK_GATE_PIE_PRESERVED', bool(ed.get_game_world()))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),
    'Automation RunTests Prophecy.Jolt.ContactShapes.AttackSweepGate+Prophecy.Jolt.ContactShapes.SelectiveSweeps+Prophecy.Agent.PhysicalContext.SelectionAndAttacks')
