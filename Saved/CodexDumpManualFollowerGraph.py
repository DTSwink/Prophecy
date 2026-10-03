import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(
    world, "prophecy.Editor.DumpManualFollowerGraph")
print("MANUAL_FOLLOW_GRAPH_DUMP_REQUESTED")
