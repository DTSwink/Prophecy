import unreal
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
assert hasattr(unreal.ProphecyAgent, 'set_attack_hand_clamp')
unreal.SystemLibrary.execute_console_command(world, 'Automation RunTests Prophecy.NN.PhysicalTargets.AttackHandClamp')
