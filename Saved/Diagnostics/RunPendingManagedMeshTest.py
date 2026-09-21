import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world=ed.get_editor_world() or ed.get_game_world()
unreal.SystemLibrary.execute_console_command(world,'Automation RunTests Prophecy.Jolt.SceneCollision.PendingManagedMesh')
