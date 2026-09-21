import unreal
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
tests = 'Prophecy.Jolt.BodyComponent.RuntimeChannels+Prophecy.Jolt.BodyComponent.CharacterRuntimeChannels+Prophecy.Jolt.Collision.RuntimeUpdateAtomicityAndSleepingContact+Prophecy.Jolt.SceneCollision.RuntimeChannels'
unreal.SystemLibrary.execute_console_command(world, 'Automation RunTests ' + tests)
print('Requested four isolated runtime collision-channel checks.')
