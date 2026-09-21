import unreal,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world()
print('PIE',bool(w))
print('STATE_ENUM',unreal.find_object(None,'/Script/GameAnimationSample3.EProphecyAgentState'))
print('STATE_FUNCTION',unreal.find_object(None,'/Script/GameAnimationSample3.ProphecyNNDefenseLibrary:GetAgentState'))
if w:
 for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
  if not a.has_valid_agent_handle():continue
  status=unreal.ProphecyNNDefenseLibrary.get_nn_defense_status(a)
  print(a.get_name(),'mode',a.get_simulation_mode(),'defense',str(status),'target',str(a.get_nn_attack_target()))
