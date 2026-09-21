import unreal
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
cls = unreal.load_class(None, '/Script/GameAnimationSample3.ProphecyJoltStaticMeshLibrary')
assert cls
print('JOLT_STATIC_MESH_LIBRARY', cls)
unreal.SystemLibrary.execute_console_command(world,
    'Automation RunTests Prophecy.Jolt.BodyComponent.AddedStaticMeshLaunch+Prophecy.Jolt.BodyComponent.SharedStepQueryAndCleanup')
