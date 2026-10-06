import unreal,json,pathlib,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SwordOwnerPhase20261006'
s={'world':None,'last':None,'start':time.monotonic(),'rows':[],'agents':[]}
def v(x):return [x.x,x.y,x.z]
def tr(x):return {'p':v(x.translation),'q':[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w],'s':v(x.scale3d)}
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 if s['world'] is not None and ed.get_game_world()==s['world']:
  unreal.SystemLibrary.execute_console_command(s['world'],'Prophecy.Reset.HitAudit sample')
  (p/'hits.json').write_bytes((p.parent/'ResetHitAudit.json').read_bytes())
  unreal.SystemLibrary.execute_console_command(s['world'],'Prophecy.Reset.HitAudit stop')
  level.editor_request_end_play()
 (p/'capture.json').write_text(json.dumps({'reason':reason,'rows':s['rows']},separators=(',',':')))
 print('SWORD_HEAD_DONE',reason,len(s['rows']))
def tick(_):
 try:
  if time.monotonic()-s['start']>90:finish('timeout');return
  w=ed.get_game_world()
  if not w:
   if s['world'] is not None:finish('world ended')
   return
  if s['world'] is None:s['world']=w
  if w!=s['world']:finish('world replaced');return
  player=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(player,unreal.ProphecyAgent):return
  n=int(player.get_editor_property('absolute tick debug'))
  if n==s['last']:return
  s['last']=n
  if not s['agents']:
   s['agents']=list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent))
   unreal.SystemLibrary.execute_console_command(w,'Prophecy.Reset.HitAudit start')
  for a in s['agents']:
   if not a.has_valid_agent_handle():continue
   at=a.get_nn_attack_state()
   r={'tick':n,'actor':a.get_name(),'player':a==player,'attack':[str(at[0]),*at[1:]] if at else None,'bones':{}}
   for bone in ['head','hand_r','lowerarm_r','hand_l','pelvis','sword']:
    b=a.get_physical_body_state(bone)
    if b:r['bones'][bone]={'transform':tr(b[0]),'v':v(b[1]),'w':v(b[2])}
   sw=a.get_held_sword()
   if sw:
    c=sw.get_component_by_class(unreal.StaticMeshComponent)
    r['sword']={'name':sw.get_name(),'transform':tr(c.get_world_transform()),'bounds':[v(x) for x in c.get_local_bounds()],'object':str(c.get_collision_object_type()),'collision':str(c.get_collision_enabled()),'responses':[str(c.get_collision_response_to_channel(x)) for x in [unreal.CollisionChannel.ECC_PAWN,unreal.CollisionChannel.ECC_PHYSICS_BODY,unreal.CollisionChannel.ECC_WORLD_DYNAMIC]]}
   s['rows'].append(r)
  if n>=120:finish('complete')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play();print('SWORD_HEAD_STARTED')
