import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Blood.NativeQueryExperiment')
print('BLOOD_NATIVE_QUERY_EXPERIMENT_REQUESTED')
