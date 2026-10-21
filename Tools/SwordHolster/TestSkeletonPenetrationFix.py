import unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), "User Play is active"
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), "Prophecy.Editor.LiveAgentTypes Inspect")
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), "Automation RunTests Prophecy.Jolt.SceneCollision.PlacedMannequin")
print("SKELETON_PENETRATION_TEST_STARTED")
