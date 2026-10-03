import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if not world:
    raise RuntimeError("PIE is not running")
unreal.SystemLibrary.execute_console_command(world, "HighResShot 1")
print("CURRENT_PIE_SCREENSHOT_REQUESTED")
