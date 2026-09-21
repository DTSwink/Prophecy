import unreal
sub=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not sub.get_game_world(), 'Stop PIE before checks'
unreal.SystemLibrary.execute_console_command(sub.get_editor_world(),
    'Automation RunTests Prophecy.Jolt.Servo+Prophecy.Jolt.PhysicsCommands+Prophecy.Jolt.RigWorld+Prophecy.Jolt.MultiRig')
print('HAND_FINAL_CHECKS_REQUESTED')
