import unreal; e=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem); assert e.get_game_world() is None; unreal.SystemLibrary.collect_garbage(); print("Collected unused editor objects")
