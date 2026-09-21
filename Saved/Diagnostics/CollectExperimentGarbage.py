import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if ed.get_game_world():
    print('Preserving active Play; no collection requested.')
else:
    unreal.SystemLibrary.collect_garbage()
    print('Collected unreferenced objects after owned diagnostic Play sessions; no asset save/restart.')
