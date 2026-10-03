import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
# These scoped native tests use value fixtures or their own temporary editor worlds.
# No test starts/stops PIE or modifies an actor in the user's world.
print('ARMED_FOREARM_USER_PLAY_PRESERVED',bool(ed.get_game_world()))
tests=['Prophecy.NN.ArmedPose','Prophecy.NN.PhysicalTargets.ForearmRollFromUpperArm','Prophecy.NN.PhysicalTargets.SpecialForearmBoundary','Prophecy.NN.PhysicalTargets.DefenseForearmBoundary']
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests '+'+'.join(tests))
print('ARMED_FOREARM_CHECKS')
