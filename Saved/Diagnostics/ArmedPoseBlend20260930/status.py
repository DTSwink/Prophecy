import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('ARMED_BLEND_PLAY_ACTIVE',bool(ed.get_game_world()))
