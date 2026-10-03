import unreal,builtins,pathlib,json,time,traceback,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
owns=not bool(ed.get_game_world())
label=sys.argv[1] if len(sys.argv)>1 else 'before'
assert owns or not label.startswith('no_'),'Experimental change requires an owned diagnostic session'
s=dict(rows=[],contacts=[],last=None,wall=time.monotonic(),done=False)
builtins._sim_rotation_mismatch=s
bones=json.loads((pathlib.Path(unreal.Paths.project_dir())/'Tools/NN/Fixtures/SlashTrain2026092223.json').read_text())['initial_history']['bone_names']
def tr(x):return dict(p=[x.translation.x,x.translation.y,x.translation.z],q=[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w])
def finish(reason):
 if s['done']:return
 s['done']=True
 unreal.unregister_slate_post_tick_callback(s['cb'])
 if s.get('bound'):
  try:s['bound'].on_component_hit.remove_callable(onhit)
  except Exception:pass
 pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics',f'SimRotationMismatch-{label}.json').write_text(json.dumps(dict(reason=reason,rows=s['rows'],contacts=s['contacts']),separators=(',',':')))
 print('SIM_ROTATION_CAPTURE_DONE',label,reason,len(s['rows']))
 s['rows'].clear()
 if owns and ed.get_game_world():unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
def onhit(component,other,other_component,impulse,hit):
 s['contacts'].append(dict(t=unreal.GameplayStatics.get_time_seconds(ed.get_game_world()),other=other.get_name() if other else None,component=other_component.get_name() if other_component else None,channel=str(other_component.get_collision_object_type()) if other_component else None,my_bone=str(hit.my_bone_name),bone=str(hit.bone_name),point=[hit.impact_point.x,hit.impact_point.y,hit.impact_point.z]))
def tick(_):
 try:
  w=ed.get_game_world()
  if not w:
   if s['rows'] or time.monotonic()-s['wall']>45:finish('World ended')
   return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if time.monotonic()-s['wall']>90:finish('Timeout');return
  if t==s['last']:return
  s['last']=t
  for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
   if not a.is_player_controlled():continue
   if label=='contacts' and not s.get('bound'):
    s['bound']=a.get_pose_reference_mesh()
    s['bound'].on_component_hit.add_callable(onhit)
   r=dict(t=t,tick=int(a.get_editor_property('tick debug')),mode=str(a.get_simulation_mode()),attack=str(a.get_nn_attack_state()),targets={},meshes={},full={})
   r['angular_global']=a.get_editor_property('world_magnetization_angular_strength_scale')
   r['magnetization']={b:str(a.get_body_magnetization_settings(b)) for b in ('calf_l','foot_l','calf_r','foot_r','hand_l','hand_r')}
   if r['tick']==40:
    mesh=a.get_pose_reference_mesh()
    r['constraints']=[dict(bones=str(unreal.ConstraintInstanceBlueprintLibrary.get_attached_body_names(c)),angular=str(unreal.ConstraintInstanceBlueprintLibrary.get_angular_limits(c))) for c in mesh.get_constraints(True)]
    location=mesh.get_socket_location('foot_r')
    result=unreal.SystemLibrary.line_trace_single(w,location+unreal.Vector(0,0,50),location-unreal.Vector(0,0,200),unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,True,[a],unreal.DrawDebugTrace.NONE,True)
    r['ground_trace']=str(result)
   meshes=list(a.get_components_by_class(unreal.SkinnedMeshComponent))
   debug=a.get_kinematic_debug_mesh()
   if debug and debug not in meshes:meshes.append(debug)
   for m in meshes:
    r['meshes'][m.get_name()]={b:tr(m.get_socket_transform(b,unreal.RelativeTransformSpace.RTS_WORLD)) for b in bones if m.get_bone_index(b)>=0}
   for b in bones:
    target=a.get_authored_body_world_target(b)
    if target:r['targets'][b]=dict(previous=tr(target[0]),future=tr(target[1]),target=tr(target[2]),alpha=target[3])
   pose=a.read_nn_future_world_pose()
   if pose:
    names,future,presented,alpha=pose
    r['full']={str(b):tr(presented[i]) for i,b in enumerate(names)}
    r['alpha']=alpha
   s['rows'].append(r)
   if label=='no_world_contact' and r['tick']==55:
    a.get_pose_reference_mesh().set_collision_response_to_all_channels(unreal.CollisionResponseType.ECR_IGNORE)
   if label=='no_static_contact' and r['tick']==55:
    a.get_pose_reference_mesh().set_collision_response_to_channel(unreal.CollisionChannel.ECC_WORLD_STATIC,unreal.CollisionResponseType.ECR_IGNORE)
   if label=='no_self_contact' and r['tick']==55:
    print('SELF_COLLISION_TEST',a.set_jolt_self_collision_enabled(False))
   if label=='no_dynamic_contact' and r['tick']==55:
    a.get_pose_reference_mesh().set_collision_response_to_channel(unreal.CollisionChannel.ECC_WORLD_DYNAMIC,unreal.CollisionResponseType.ECR_IGNORE)
   if label=='no_physics_body_contact' and r['tick']==55:
    a.get_pose_reference_mesh().set_collision_response_to_channel(unreal.CollisionChannel.ECC_PHYSICS_BODY,unreal.CollisionResponseType.ECR_IGNORE)
   if label=='no_floor_contact' and r['tick']==55:
    a.get_pose_reference_mesh().set_collision_response_to_channel(unreal.CollisionChannel.ECC_FLOOR,unreal.CollisionResponseType.ECR_IGNORE)
  if len(s['rows'])>=360:finish('Complete')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
if owns:unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('SIM_ROTATION_CAPTURE_STARTED',label)



