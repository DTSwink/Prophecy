import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
unreal.SystemLibrary.collect_garbage()
print('REQUESTED_COLLECTION_OF_UNREFERENCED_OBJECTS')
