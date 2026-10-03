import unreal
if not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world():
    unreal.SystemLibrary.collect_garbage()
    print('Collected unused editor objects')
