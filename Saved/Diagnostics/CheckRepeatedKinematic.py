import unreal, time, traceback, math
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user Play'
s=dict(frames=0,calls=0,last=None,wall=time.monotonic(),states={})
bones=('pelvis','spine_05','hand_r','foot_r')
def pose(mesh):
 out=[]
 for bone in bones:
  t=mesh.get_socket_transform(bone,unreal.RelativeTransformSpace.RTS_WORLD)
  out.extend((t.translation.x,t.translation.y,t.translation.z,t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w))
 return out
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 if ed.get_game_world():level.editor_request_end_play()
 print('REPEATED_KIN_DONE',reason,s)
def tick(_):
 try:
  w=ed.get_game_world()
  if not w:
   if time.monotonic()-s['wall']>30:finish('No world')
   return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if s['last']==t:return
  s['last']=t;s['frames']+=1
  for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
   if not a.is_player_controlled():continue
   mode=a.get_simulation_mode();s['states'][str(mode)]=s['states'].get(str(mode),0)+1
   if s['frames']<=6:continue
   assert mode==unreal.ProphecyAgentSimulationMode.KINEMATIC, (str(mode),a.get_editor_property('tick debug'))
   meshes=a.get_components_by_class(unreal.SkeletalMeshComponent)
   before=[pose(m) for m in meshes];anims=[m.get_anim_instance() for m in meshes]
   for i in range(10):
    assert a.set_simulation_mode(mode)
    s['calls']+=1
   assert before==[pose(m) for m in meshes], 'Same-mode call changed pose'
   assert anims==[m.get_anim_instance() for m in meshes], 'Same-mode call replaced anim instance'
   assert all(math.isfinite(v) for p in before for v in p), 'Nonfinite pose'
  if s['frames']>=210:finish('PASS' if s['calls'] else 'No agent')
  elif time.monotonic()-s['wall']>60:finish('Timeout')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('REPEATED_KIN_STARTED')
