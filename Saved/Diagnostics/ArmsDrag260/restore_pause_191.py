import unreal,time
pause_editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
pause_level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not pause_editor.get_game_world(),'Preserve any newly started user PIE'
pause_state={'start':time.monotonic()}
def restore_pause_tick(_):
 w=pause_editor.get_game_world()
 if time.monotonic()-pause_state['start']>60:
  unreal.unregister_slate_post_tick_callback(pause_state['cb']);print('RESTORE_PAUSE_TIMEOUT');return
 if not w:return
 for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
  if a.is_player_controlled() and int(a.get_editor_property('tick debug'))>=191:
   unreal.GameplayStatics.set_game_paused(w,True)
   unreal.unregister_slate_post_tick_callback(pause_state['cb'])
   print('RESTORED_PAUSE_AT_TICK',a.get_editor_property('tick debug'))
   return
pause_state['cb']=unreal.register_slate_post_tick_callback(restore_pause_tick)
pause_level.editor_request_begin_play()
print('Restoring play paused at tick191 with the corrected release')
