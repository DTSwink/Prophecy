import unreal
sub=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not sub.get_game_world()
agent=unreal.get_default_object(unreal.ProphecyAgent)
assert callable(agent.set_physical_joint_angular_limits)
assert callable(agent.reset_physical_joint_angular_limits)
unreal.SystemLibrary.execute_console_command(sub.get_editor_world(),
 'Automation RunTests Prophecy.Jolt.Character.AngularLimitControls+Prophecy.Jolt.RigWorld.LiveAngularLimitsAtomic')
print('RUNTIME_JOINT_LIMIT_CHECKS_REQUESTED')
