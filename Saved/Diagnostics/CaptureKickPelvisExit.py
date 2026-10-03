import unreal,pathlib,json,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
s=dict(start=time.monotonic(),last=None,frame=0,rows=[])
def v(x):return [x.x,x.y,x.z]
def tr(x):return dict(p=v(x.translation),q=[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w])
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/KickPelvisExit.json').write_text(json.dumps(dict(reason=reason,rows=s['rows']),separators=(',',':')))
 print('KICK_PELVIS_EXIT_DONE',reason,len(s['rows']))
 if ed.get_game_world():level.editor_request_end_play()
def tick(_):
 try:
  if time.monotonic()-s['start']>150:finish('Timeout');return
  w=ed.get_game_world()
  if not w:return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t;s['frame']+=1
  for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
   r=dict(frame=s['frame'],tick=int(a.get_editor_property('tick debug')),t=t,actor=a.get_name(),player=a.is_player_controlled(),attack=str(a.get_nn_attack_state()),weights=list(a.get_locomotion_checkpoint_weights()),bones={})
   for b in ('pelvis','foot_l','foot_r'):
    body=a.get_physical_body_state(b);target=a.get_authored_body_world_target(b);d={}
    if body:d.update(physical=tr(body[0]),velocity=v(body[1]))
    if target:d.update(previous=tr(target[0]),future=tr(target[1]),target=tr(target[2]),alpha=target[3])
    r['bones'][b]=d
   s['rows'].append(r)
  if s['frame']>=620:finish('Complete')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('KICK_PELVIS_EXIT_STARTED')
