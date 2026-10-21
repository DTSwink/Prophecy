import unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), "User Play is active"
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), "Automation RunTests Prophecy.Blood.RectangleIntegration")
print("INJURY_PROJECTION_TEST_STARTED")
