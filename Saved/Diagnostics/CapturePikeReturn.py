import unreal,pathlib,json,time,traceback,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
tag=sys.argv[1] if len(sys.argv)>1 else 'fixed'
comparison=int(sys.argv[2]) if len(sys.argv)>2 else 1
both=len(sys.argv)>3 and sys.argv[3]=='on'
force=len(sys.argv)>3
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySlashReturnLibrary'))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.SlashReturn.UnarmedShortestRotation '+str(comparison))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.SlashReturn.Audit 1')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.SlashReturn.ClearPathShortcut '+('0' if tag.startswith('legacy') else '1'))
s=dict(rows=[],last=None,wall=time.monotonic(),frame=0)
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/PikeReturn';out.mkdir(exist_ok=True)
bones=('clavicle_l','clavicle_r','neck_01','pelvis','spine_05','upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r')
def tr(x):return dict(p=[x.translation.x,x.translation.y,x.translation.z],q=[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w])
def finish(reason):
 unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.SlashReturn.Audit 0')
 unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.SlashReturn.ClearPathShortcut 1')
 unreal.unregister_slate_post_tick_callback(s['cb'])
 (out/(tag+'.json')).write_text(json.dumps(dict(reason=reason,rows=s['rows']),separators=(',',':')))
 unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.SlashReturn.UnarmedShortestRotation 1')
 if ed.get_game_world():level.editor_request_end_play()
 print('FOREARM_EXIT_DONE',reason,len(s['rows']))
 s['rows'].clear()
def tick(_):
 try:
  w=ed.get_game_world()
  if not w:
   if time.monotonic()-s['wall']>60:finish('No world')
   return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t;s['frame']+=1
  if tag=='latelegacy_variants' and s['frame']==486:
   unreal.SystemLibrary.execute_console_command(w,'Prophecy.SlashReturn.ClearPathShortcut 0')
  if 'variants' in tag and s['frame']==30:
   actors=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
   for a in actors:assert a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
   for a in actors:a.set_actor_tick_enabled(False);a.stop_nn_attack()
  for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
   if 'variants' in tag and a.is_player_controlled() and s['frame'] in [90,180,270,360,450,540,630]:
    variant=['slashL','slashR','slashLD','slashRD','slashLU','slashRU','pike'][s['frame']//90-1]
    target=a.get_actor_location()+a.get_actor_forward_vector()*100.+unreal.Vector(0,0,70)
    assert a.trigger_nn_attack(variant,target,False,None)
   if force and a.is_player_controlled() and s['frame']==160:
    # PIE instance only: force the second choice without changing the graph,
    # target generation, checkpoint, physics or recovery settings.
    for name in ('attack list','slash list','melee list'):
     values=a.get_editor_property(name)
     values.clear();values.append(unreal.Name('slashRU'))
     assert list(a.get_editor_property(name))==[unreal.Name('slashRU')],name
    assert lib.call_method('SetAttackBothArmsReturnToNeutral',(a,*(i==5 for i in range(16))))
    assert lib.call_method('SetBothArmsReturnToNeutralEnabled',(a,both))
    print('BOTH_ARM_TEST_CONFIGURED',both,a.get_name())
   pose=a.read_nn_future_world_pose()
   if not pose:continue
   names,future,presented,alpha=pose
   state=a.get_nn_attack_state()
   r=dict(frame=s['frame'],t=t,actor=a.get_name(),possessed=a.is_player_controlled(),attack=str(state),pose={str(b):dict(future=tr(future[i]),presented=tr(presented[i])) for i,b in enumerate(names) if str(b) in bones},meshes={})
   try:r['tick']=int(a.get_editor_property('tick debug'))
   except:pass
   sword=a.get_held_sword()
   if sword:
    for m in sword.get_components_by_class(unreal.StaticMeshComponent):
     if m.get_name()=='sword' and m.static_mesh:
      box=m.static_mesh.get_bounding_box();grip=a.get_editor_property('sword_grip_transform')
      r['weapon']=dict(actual=tr(m.get_world_transform()),grip=tr(grip),scale=[grip.scale3d.x,grip.scale3d.y,grip.scale3d.z],min=[box.min.x,box.min.y,box.min.z],max=[box.max.x,box.max.y,box.max.z])
   for m in a.get_components_by_class(unreal.SkeletalMeshComponent):
    if m.get_bone_index('hand_l')>=0:r['meshes'][m.get_name()]={b:tr(m.get_socket_transform(b,unreal.RelativeTransformSpace.RTS_WORLD)) for b in bones}
   s['rows'].append(r)
  if s['frame']>=(720 if 'variants' in tag else 360):finish('Complete')
  elif time.monotonic()-s['wall']>130:finish('Timeout')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
print('FOREARM_EXIT_STARTED')
