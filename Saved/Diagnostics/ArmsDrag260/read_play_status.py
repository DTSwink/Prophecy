import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('Wrist status: user PIE active=',bool(ed.get_game_world()))
