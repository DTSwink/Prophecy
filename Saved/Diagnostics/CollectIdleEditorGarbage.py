import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if ed.get_game_world():
    print('Preserving active Play; no collection requested.')
else:
    unreal.SystemLibrary.collect_garbage()
    print('Collected unused editor objects; no asset saves or restart.')
