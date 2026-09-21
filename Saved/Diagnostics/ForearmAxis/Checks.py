import unreal
s=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not s.get_game_world()
unreal.SystemLibrary.execute_console_command(s.get_editor_world(), 'Automation RunTests Prophecy.Jolt.Joints+Prophecy.Jolt.Character.AngularLimitControls+Prophecy.Jolt.RigWorld.LiveAngularLimitsAtomic')
print('WRIST_REGRESSION_CHECKS_REQUESTED')
