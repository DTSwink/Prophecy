import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('EDITOR_WORLD',ed.get_editor_world().get_path_name())
print('GAME_WORLD',ed.get_game_world())
