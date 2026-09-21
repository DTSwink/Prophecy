import unreal,time,json,pathlib,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world()
s={'rows':[],'start':time.monotonic()}
def tick(dt):
 try:
  w=ed.get_game_world()
  if not w:return
  p=unreal.GameplayStatics.get_player_pawn(w,0)
  if not p:return
  t=unreal.GameplayStatics.get_time_seconds(w)
  sword=p.get_held_sword()
  s['rows'].append({'t':t,'sword':sword.get_name() if sword else None,'ready':p.has_valid_agent_handle(),'mode':str(p.get_simulation_mode()),'tick':p.get_editor_property('tick debug')})
  if sword:
   m=sword.get_editor_property('root_component'); pos=m.get_world_location(); hand=p.get_physical_body_state('hand_r')[0].translation
   s['rows'][-1].update(visible=m.is_visible(),hidden=sword.get_editor_property('hidden'),mesh=m.get_editor_property('static_mesh').get_path_name(),position=[pos.x,pos.y,pos.z],hand_distance=(pos-hand).length())
  if t<2:return
  print('SWORD_STARTUP',json.dumps(s['rows'][::20]))
  pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/SwordStartupCurrent.json').write_text(json.dumps(s['rows']))
  unreal.unregister_slate_post_tick_callback(s['cb']);level.editor_request_end_play()
 except Exception:
  print(traceback.format_exc());unreal.unregister_slate_post_tick_callback(s['cb']);level.editor_request_end_play()
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()

