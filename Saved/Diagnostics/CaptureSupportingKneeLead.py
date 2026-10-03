import unreal,builtins,pathlib,json,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
s=dict(rows=[],last=None,wall=time.monotonic(),owned=not bool(ed.get_game_world()))
builtins._supporting_knee_lead=s
bones=('pelvis','thigh_l','calf_l','foot_l','ball_l','thigh_r','calf_r','foot_r','ball_r')
def tr(x):return dict(p=[x.translation.x,x.translation.y,x.translation.z],q=[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w])
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SupportingKneeLead-live.json'
 p.write_text(json.dumps(dict(reason=reason,rows=s['rows']),separators=(',',':')),encoding='utf-8')
 print('SUPPORTING_KNEE_CAPTURE_DONE',reason,len(s['rows']))
 s['rows'].clear()
 if s['owned'] and ed.get_game_world():unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
def tick(_):
 try:
  w=ed.get_game_world()
  if not w:
   if s['rows'] or time.monotonic()-s['wall']>30:finish('Play ended or unavailable')
   return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:
   if time.monotonic()-s['wall']>45:finish('Paused timeout')
   return
  s['last']=t
  for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
   if not a.is_player_controlled():continue
   r=dict(t=t,tick=int(a.get_editor_property('tick debug')),attack=str(a.get_nn_attack_state()),mode=str(a.get_simulation_mode()),meshes={},targets={})
   for m in a.get_components_by_class(unreal.SkeletalMeshComponent):
    r['meshes'][m.get_name()]={b:tr(m.get_socket_transform(b,unreal.RelativeTransformSpace.RTS_WORLD)) for b in bones if m.get_bone_index(b)>=0}
   for b in bones:
    target=a.get_authored_body_world_target(b)
    if target:r['targets'][b]=tr(target[2])
   s['rows'].append(r)
  if len(s['rows'])>=360:finish('Complete')
  elif time.monotonic()-s['wall']>45:finish('Timeout')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
if s['owned']:unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('SUPPORTING_KNEE_CAPTURE_ATTACHED_NO_SETTINGS_CHANGES')
