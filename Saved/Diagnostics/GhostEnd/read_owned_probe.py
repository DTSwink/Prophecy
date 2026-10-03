import unreal
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if w:
 for actor in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
  if actor.is_player_controlled():print('OWNED_PROBE_STATE',actor.get_nn_attack_state())
