import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world()
print('KNEE_INSPECT',bool(w))
if w:
 for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
  print(a.get_name(),a.is_player_controlled(),a.get_editor_property('tick debug'))
