import unreal
e=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=e.get_game_world()
print('USER_PIE',bool(w))
if w:
 for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
  if a.is_player_controlled():print('PLAYER_TICK',a.get_editor_property('tick debug'))
