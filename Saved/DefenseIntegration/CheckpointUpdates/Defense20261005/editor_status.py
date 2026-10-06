import unreal,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print(json.dumps(dict(play=ed.get_game_world() is not None,map=ed.get_editor_world().get_name())))
