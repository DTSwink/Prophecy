import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve Play'
w=ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RefreshSharedEntryFeet')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RepairLibraryDefaults')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.SystemLibrary.execute_console_command(w,'Automation RunTests Prophecy.NN.PhysicalTargets.RecoveryCalfLength')
print('SHARED_ENTRY_FEET_REFRESHED_TEST_QUEUED')
