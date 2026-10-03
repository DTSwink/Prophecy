import unreal,builtins
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world()
if w:
 for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
  if a.is_player_controlled():
   print('CLOCK',a.get_name(),'time',unreal.GameplayStatics.get_time_seconds(w),'debug_tick',a.get_editor_property('tick debug'))
s=getattr(builtins,'_calf_connection',{})
print('CAPTURE',s.get('owned'),len(s.get('rows',[])),s.get('start'))
