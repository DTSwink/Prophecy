import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Preserving user Play; run isolated checks after Play ends.'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),
    'Automation RunTests Prophecy.NN.PhysicalTargets.KickLeewayInheritance+Prophecy.NN.PhysicalTargets.AttackLegClamps+Prophecy.Joints.KickFootLeeway')
