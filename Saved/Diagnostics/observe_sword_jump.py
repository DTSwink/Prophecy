import unreal,json,pathlib,time,traceback,builtins
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'User PIE is running.'
s={'rows':[],'start':time.monotonic(),'paused':False};builtins._sword_jump_observation=s
def v(x):return [x.x,x.y,x.z]
def tr(x):return dict(p=v(x.translation),q=[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w],scale=v(x.scale3d))
def finish(err=''):
 unreal.unregister_slate_post_tick_callback(s['cb']);level.editor_request_end_play()
 pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/SwordJump_current_observed.json').write_text(json.dumps(dict(rows=s['rows'],error=err)))
 print('SWORD_OBSERVATION_FINISHED',len(s['rows']),err)
def tick(dt):
 try:
  w=ed.get_game_world()
  if not w:return
  if s['paused']:return
  a=unreal.GameplayStatics.get_player_pawn(w,0)
  if not a:return
  t=unreal.GameplayStatics.get_time_seconds(w);sword=a.get_held_sword()
  r=dict(t=t,tick=a.get_editor_property('tick debug'),root=tr(a.get_actor_transform()),bones={})
  for bone in ['pelvis','upperarm_r','lowerarm_r','hand_r']:
   b=a.get_physical_body_state(bone)
   if b:r['bones'][bone]=dict(transform=tr(b[0]),v=v(b[1]),av=v(b[2]))
  if sword:
   m=sword.get_editor_property('root_component');r['sword']=dict(transform=tr(m.get_world_transform()),velocity=v(m.get_physics_linear_velocity()),visible=m.is_visible())
  if not s['rows']:
   r['cubes']=[dict(name=c.get_name(),transform=tr(c.get_actor_transform())) for c in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.StaticMeshActor)]
  s['rows'].append(r)
  if r['tick']>=89 and not s.get('passed_pause'):
   s['paused']=True;unreal.GameplayStatics.set_game_paused(w,True);print('SWORD_PAUSED',r['tick'])
  if t>=4:finish()
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
