import unreal,builtins
s=getattr(builtins,'_calf1495',{})
print('CAPTURE_FRAME',s.get('frame'),'ROWS',len(s.get('rows',[])))
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if w:
 for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
  if a.is_player_controlled():print('BP_TICK',a.get_editor_property('tick debug'))
