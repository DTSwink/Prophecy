import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.Jolt.Query.ClosestHitsNormalsAndArguments+Prophecy.Jolt.Query.MovedPoseAndHandleLifetime')
print('Requested two native ray identity/lifetime checks')
