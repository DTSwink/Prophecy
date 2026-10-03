import unreal
print('Blueprint helpers', [x for x in dir(unreal.BlueprintEditorLibrary) if any(s in x for s in ('refresh','replace','node','graph'))])
print('PIE',bool(unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()))
