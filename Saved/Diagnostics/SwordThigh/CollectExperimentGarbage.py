import unreal
e=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not e.get_game_world()
unreal.SystemLibrary.collect_garbage()
print('Collected transient PIE garbage')
