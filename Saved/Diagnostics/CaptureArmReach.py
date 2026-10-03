import unreal,pathlib,json,time,traceback,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
tag=sys.argv[1] if len(sys.argv)>1 else 'before'
variant_test=tag.startswith('variants')
owned=not bool(ed.get_game_world())
if variant_test:assert owned,'Do not alter user Play'
late_route=tag=='route_latefix'
if late_route:assert owned,'Do not alter user Play'
if late_route:unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.SlashReturn.BodyRoute 0')
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/ArmReach';out.mkdir(exist_ok=True)
log=pathlib.Path(unreal.Paths.project_saved_dir())/'Logs/GameAnimationSample3.log'
s=dict(rows=[],last=None,wall=time.monotonic(),frame=0,offset=log.stat().st_size)
bones=('clavicle_l','clavicle_r','neck_01','pelvis','spine_05','upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r')
def tr(x):return dict(p=[x.translation.x,x.translation.y,x.translation.z],q=[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w])
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.SlashReturn.Audit 1')
def finish(reason):
 unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.SlashReturn.Audit 0')
 if tag=='variants_latelegacy':unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.SlashReturn.Refined 1')
 if late_route:unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.SlashReturn.BodyRoute 1')
 unreal.unregister_slate_post_tick_callback(s['cb'])
 (out/(tag+'.json')).write_text(json.dumps(dict(reason=reason,owned=owned,rows=s['rows']),separators=(',',':')))
 with log.open('rb') as f:f.seek(s['offset']);(out/(tag+'.log')).write_bytes(f.read())
 if owned and ed.get_game_world():level.editor_request_end_play()
 print('ARM_REACH_DONE',tag,reason,len(s['rows']))
 s['rows'].clear()
def tick(_):
 try:
  w=ed.get_game_world()
  if not w:
   if s['frame'] or time.monotonic()-s['wall']>60:finish('No world')
   return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t;s['frame']+=1
  if late_route and s['frame']==252:unreal.SystemLibrary.execute_console_command(w,'Prophecy.SlashReturn.BodyRoute 1')
  if tag=='variants_latelegacy' and s['frame']==486:
   unreal.SystemLibrary.execute_console_command(w,'Prophecy.SlashReturn.Refined 0')
  if variant_test and s['frame']==30:
   actors=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
   for a in actors:assert a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
   for a in actors:a.set_actor_tick_enabled(False);a.stop_nn_attack()
   lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySlashReturnLibrary'))
   for a in actors:
    if a.is_player_controlled():
     assert lib.call_method('SetAttackBothArmsReturnToNeutral',(a,*([True]*16)))
     assert lib.call_method('SetBothArmsReturnToNeutralEnabled',(a,True))
  for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
   if not a.is_player_controlled():continue
   if variant_test and s['frame'] in [90,180,270,360,450,540,630]:
    attack=['slashL','slashR','slashLD','slashRD','slashLU','slashRU','pike'][s['frame']//90-1]
    target=a.get_actor_location()+a.get_actor_forward_vector()*100.+unreal.Vector(0,0,70)
    assert a.trigger_nn_attack(attack,target,False,None)
   pose=a.read_nn_future_world_pose()
   if not pose:continue
   names,future,presented,alpha=pose
   r=dict(frame=s['frame'],t=t,actor=a.get_name(),possessed=True,attack=str(a.get_nn_attack_state()),pose={str(b):dict(future=tr(future[i]),presented=tr(presented[i])) for i,b in enumerate(names) if str(b) in bones})
   try:r['tick']=int(a.get_editor_property('tick debug'))
   except:pass
   sword=a.get_held_sword()
   if sword:
    for m in sword.get_components_by_class(unreal.StaticMeshComponent):
     if m.get_name()=='sword' and m.static_mesh:
      box=m.static_mesh.get_bounding_box();grip=a.get_editor_property('sword_grip_transform')
      r['weapon']=dict(actual=tr(m.get_world_transform()),grip=tr(grip),scale=[grip.scale3d.x,grip.scale3d.y,grip.scale3d.z],min=[box.min.x,box.min.y,box.min.z],max=[box.max.x,box.max.y,box.max.z])
   s['rows'].append(r)
  if s['frame']>=(720 if variant_test else 360):finish('Complete')
  elif time.monotonic()-s['wall']>150:finish('Timeout')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
if owned:level.editor_request_begin_play()
print('ARM_REACH_STARTED',tag,'owned',owned)
