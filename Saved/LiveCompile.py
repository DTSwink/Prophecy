import unreal

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world, "LiveCoding.Compile")
print("LIVE_CODING_REQUESTED")
