import unreal,time,json,pathlib
view_ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
view_level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert view_ed.get_game_world() is None
view_state=dict(world=None,paused=False,start=time.monotonic())
unreal._ghost_loco_view_state=view_state
view_lib=unreal.get_default_object(unreal.ProphecyAttackFootLocomotionLibrary)
def finish_ghost_view():
 unreal.unregister_slate_post_tick_callback(view_state['callback'])
 if view_ed.get_game_world()==view_state['world']:view_level.editor_request_end_play()
 unreal._ghost_loco_view_state=None
 print('GHOST_VIEW_FINISHED')
def ghost_view_tick(_):
 if time.monotonic()-view_state['start']>100:finish_ghost_view();return
 world=view_ed.get_game_world()
 if world is None:
  if view_state['world'] is not None:finish_ghost_view()
  return
 if view_state['world'] is None:view_state['world']=world
 if world!=view_state['world']:finish_ghost_view();return
 if view_state['paused']:return
 actor=unreal.GameplayStatics.get_player_pawn(world,0)
 if not isinstance(actor,unreal.ProphecyAgent):return
 clock=int(actor.get_editor_property('tick debug'))
 if clock<168:return
 ghost=view_lib.call_method('ReadGhostLocoDrag',(actor,))
 if not ghost:return
 view_lib.call_method('DrawGhostLocoDrag',(actor,True,unreal.Vector(),120.))
 view_state['paused']=True
 unreal.GameplayStatics.set_game_paused(world,True)
 p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/GhostLocoDrag20261003'
 (p/'overlay.json').write_text(json.dumps(dict(tick=clock,ghost_bones=[str(n) for n in ghost[0]],paused=True)))
 print('GHOST_VIEW_PAUSED',clock)
view_state['callback']=unreal.register_slate_post_tick_callback(ghost_view_tick)
view_state['finish']=finish_ghost_view
view_level.editor_request_begin_play()
