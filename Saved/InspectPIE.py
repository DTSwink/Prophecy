import unreal
sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
print('PIE=' + str(sub.is_in_play_in_editor()))
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
print('MAP=' + world.get_path_name())
