import unreal


world = unreal.EditorLevelLibrary.get_editor_world()
unreal.SystemLibrary.execute_console_command(world, "LiveCoding.Compile")
print("Requested Live Coding compile")
