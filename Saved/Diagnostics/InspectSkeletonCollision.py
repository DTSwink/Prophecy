import unreal,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
owned=not bool(ed.get_game_world())
s={'start':time.monotonic()}
def finish():
 unreal.unregister_slate_post_tick_callback(s['cb'])
 if owned:level.editor_request_end_play()
def tick(_):
 try:
  w=ed.get_game_world()
  if time.monotonic()-s['start']>25:finish();return
  if not w or unreal.GameplayStatics.get_time_seconds(w)<2:return
  print('SKELETON_COLLISION_STATS',w.get_path_name())
  unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.ContactExperiment collisionstats all')
  for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor):
   if 'PoseAgent' in a.get_name():
    for c in a.get_components_by_class(unreal.SkeletalMeshComponent):
     print('SKELETON',a.get_name(),c.get_name(),c.is_visible(),c.is_simulating_physics())
  finish()
 except Exception:print(traceback.format_exc());finish()
s['cb']=unreal.register_slate_post_tick_callback(tick)
if owned:level.editor_request_begin_play()
