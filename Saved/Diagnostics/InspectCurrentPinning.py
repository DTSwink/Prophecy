import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world()
if w:
 for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
  if a.is_player_controlled():
   print('PIN_TOLERANCE',unreal.ProphecyWalkPinningLibrary.get_walk_pinning_tolerance(a))
   print('PIN_LIMIT',unreal.ProphecyWalkPinningLibrary.get_walk_pinning_limit(a))
   print('FOOT_PINNING',a.get_locomotion_foot_pinning())
else: print('NO_PLAY')
