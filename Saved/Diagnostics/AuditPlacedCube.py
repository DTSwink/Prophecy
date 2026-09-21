import unreal,time
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
s={'owned':not bool(ed.get_game_world()),'start':time.monotonic()}
def tick(_):
 w=ed.get_game_world()
 if w and unreal.GameplayStatics.get_time_seconds(w)>1:
  unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.MeshAudit')
  unreal.unregister_slate_post_tick_callback(s['cb'])
  if s['owned']:level.editor_request_end_play()
 elif time.monotonic()-s['start']>30:unreal.unregister_slate_post_tick_callback(s['cb'])
s['cb']=unreal.register_slate_post_tick_callback(tick)
if s['owned']:level.editor_request_begin_play()
