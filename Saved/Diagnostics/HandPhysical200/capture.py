import unreal,pathlib,json,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/HandPhysical200'
mode=(p/'capture_mode.txt').read_text(encoding='utf8').strip() if (p/'capture_mode.txt').exists() else 'baseline'
s=dict(world=None,last=None,start=time.monotonic(),frames=0,rows=[],meta={})
bones=('pelvis','spine_05','upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r')
def vec(v):return [v.x,v.y,v.z]
def tr(t):return dict(p=vec(t.translation),q=[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w])
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 (p/(mode+'.json')).write_text(json.dumps(dict(reason=reason,meta=s['meta'],rows=s['rows']),separators=(',',':')),encoding='utf8')
 w=ed.get_game_world()
 if w is not None and w==s['world']:level.editor_request_end_play()
 print('HAND_200_CAPTURE_DONE',reason,s['frames']);s['rows'].clear()
def tick(_):
 try:
  if time.monotonic()-s['start']>90:finish('Watchdog');return
  w=ed.get_game_world()
  if w is None:
   if s['world'] is not None:finish('World ended')
   return
  if s['world'] is None:s['world']=w
  elif w!=s['world']:finish('World replaced');return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t;s['frames']+=1
  for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
   if not a.is_player_controlled():continue
   clock=int(a.get_editor_property('tick debug'))
   r=dict(tick=clock,mode=str(a.get_simulation_mode()),attack=str(a.get_nn_attack_state()),meshes={},bodies={},targets={},raw={},limits={})
   if clock==30:
    lib=unreal.ConstraintInstanceBlueprintLibrary;mesh=a.get_pose_reference_mesh()
    s['joints']={str(lib.get_attached_body_names(c)):c for c in mesh.get_constraints(True)}
    s['meta']=dict(actor=a.get_name(),jolt=a.is_jolt_physical_animation_enabled(),prediction=a.is_jolt_joint_limit_prediction_enabled(),drive=str(a.get_editor_property('PhysicalDriveSettings')),drive_multiplier=a.get_editor_property('PhysicalDriveStrengthMultiplier'),constraint_getters=[x for x in dir(lib) if x.startswith('get_')])
   for m in a.get_components_by_class(unreal.SkinnedMeshComponent):
    r['meshes'][m.get_name()]={b:tr(m.get_socket_transform(b,unreal.RelativeTransformSpace.RTS_WORLD)) for b in bones if m.get_bone_index(b)>=0}
   for b in bones:
    body=a.get_physical_body_state(b)
    if body:r['bodies'][b]=dict(transform=tr(body[0]),v=vec(body[1]),w=vec(body[2]),sim=body[3])
    target=a.get_authored_body_world_target(b)
    if target:r['targets'][b]=dict(previous=tr(target[0]),future=tr(target[1]),target=tr(target[2]),alpha=target[3])
   pose=a.read_nn_future_world_pose()
   if pose:
    names,future,presented,alpha=pose;r['alpha']=alpha
    r['raw']={str(b):dict(future=tr(future[i]),presented=tr(presented[i])) for i,b in enumerate(names) if str(b) in bones}
   if 180<=clock<=220:
    for name,c in s.get('joints',{}).items():
     if 'hand_' in name or 'lowerarm_' in name:r['limits'][name]=str(unreal.ConstraintInstanceBlueprintLibrary.get_angular_limits(c))
   if clock in (30,180,195,200,205,220):
    r['profile']=unreal.get_default_object(unreal.ProphecyPhysicalProfileLibrary).call_method('PrintPhysicalBoneProfiles',(a,0.,unreal.LinearColor(1,1,1,1)))
   s['rows'].append(r)
   # The recorded prefix is unchanged; alter only an owned PIE collision gate just before Hit.
   if clock==199:
    if mode=='no_owner_sword':unreal.get_default_object(unreal.ProphecySwordPhysicsLibrary).call_method('SetOwnSwordCollisionEnabled',(a,False))
    if mode=='no_body_self':a.set_jolt_self_collision_enabled(False)
  if s['frames']>=260:finish('Complete')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
print('HAND_200_CAPTURE_STARTED')
