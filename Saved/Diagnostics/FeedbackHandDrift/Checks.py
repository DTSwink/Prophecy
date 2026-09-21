import unreal
sub=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not sub.get_game_world()
unreal.SystemLibrary.execute_console_command(sub.get_editor_world(),
 'Automation RunTests Prophecy.Jolt.RigWorld+Prophecy.Jolt.Servo+Prophecy.Jolt.PhysicsCommands+Prophecy.Jolt.Character.RuntimeBoneMaterials+Prophecy.NN.PhysicalFeedbackTolerance')
print('FEEDBACK_HAND_CHECKS_REQUESTED')
