import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user PIE'
w=ed.get_editor_world()
if w.get_path_name().startswith('/Game/mybasic.'):
 dirty=unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
 assert not dirty,'Preserve dirty map rather than unload it'
 assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('/Game/testNN')
print('RETURNED_EDITOR_MAP',ed.get_editor_world().get_path_name())
