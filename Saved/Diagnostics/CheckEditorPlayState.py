import unreal
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
print('ACTIVE_PLAY_WORLD=' + (world.get_path_name() if world else 'NONE'))
