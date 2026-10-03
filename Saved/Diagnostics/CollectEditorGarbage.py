import unreal
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
unreal.SystemLibrary.collect_garbage()
print('UNREFERENCED_EDITOR_OBJECT_COLLECTION_REQUESTED')
