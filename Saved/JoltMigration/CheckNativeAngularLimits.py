import unreal

assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
print('Angular fighter node loaded: ' + str(hasattr(unreal.ProphecyAgent, 'set_use_authored_angular_limits')))
unreal.SystemLibrary.execute_console_command(world, 'Automation RunTests Prophecy.Jolt.RigWorld.LiveAngularLimitsAtomic')
