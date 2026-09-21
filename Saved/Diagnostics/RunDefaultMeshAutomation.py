import unreal
e=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not e.get_game_world()
unreal.SystemLibrary.execute_console_command(e.get_editor_world(),'Automation RunTests Prophecy.Jolt.SceneCollision.StandardMovableMeshes')
