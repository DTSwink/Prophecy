import unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user Play'
w = ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w, 'Prophecy.Editor.RepairLibraryDefaults')
unreal.SystemLibrary.execute_console_command(w, 'Prophecy.Editor.RefreshWalkBoundTarget')
unreal.SystemLibrary.execute_console_command(w, 'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.SystemLibrary.execute_console_command(w, 'Automation RunTests Prophecy.NN.WalkPinning')
print('WALK_BOUND_TARGET_TESTS_QUEUED')
