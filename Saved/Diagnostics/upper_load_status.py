import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('UPPER_LOAD_PIE_ACTIVE',bool(ed.get_game_world()))
print('UPPER_LOAD_EDITOR_WORLD',ed.get_editor_world().get_path_name())
