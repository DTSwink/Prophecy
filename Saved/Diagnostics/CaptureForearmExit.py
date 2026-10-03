import unreal,pathlib,json,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
s=dict(rows=[],last=None,wall=time.monotonic(),frame=0)
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/ForearmExit';out.mkdir(exist_ok=True)
bones=('pelvis','spine_05','upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r')
def tr(x):return dict(p=[x.translation.x,x.translation.y,x.translation.z],q=[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w])
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 (out/'baseline.json').write_text(json.dumps(dict(reason=reason,rows=s['rows']),separators=(',',':')))
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
  for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
   pose=a.read_nn_future_world_pose()
   if not pose:continue
   names,future,presented,alpha=pose
   state=a.get_nn_attack_state()
   r=dict(frame=s['frame'],t=t,actor=a.get_name(),possessed=a.is_player_controlled(),attack=str(state),pose={str(b):dict(future=tr(future[i]),presented=tr(presented[i])) for i,b in enumerate(names) if str(b) in bones},meshes={})
   try:r['tick']=int(a.get_editor_property('tick debug'))
   except:pass
   for m in a.get_components_by_class(unreal.SkeletalMeshComponent):
    if m.get_bone_index('hand_l')>=0:r['meshes'][m.get_name()]={b:tr(m.get_socket_transform(b,unreal.RelativeTransformSpace.RTS_WORLD)) for b in bones}
   s['rows'].append(r)
  if s['frame']>=850:finish('Complete')
  elif time.monotonic()-s['wall']>130:finish('Timeout')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
print('FOREARM_EXIT_STARTED')
