import unreal


game_world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem).get_game_world()
if not game_world:
    raise RuntimeError("No PIE game world")
unreal.SystemLibrary.execute_console_command(game_world, "Input.+Key Z")
unreal.SystemLibrary.execute_console_command(game_world, "Input.+Key LeftShift")
print("MANUAL_FOLLOW_AUDIT_RUN_INPUT_PRESSED")
