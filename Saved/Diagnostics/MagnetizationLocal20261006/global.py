import unreal,json,pathlib,time,traceback,math
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/MagnetizationLocal20261006'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
lib=unreal.ProphecyPhysicalProfileLibrary
s={'world':None,'start':time.monotonic(),'last':None,'agents':[],'rows':[],'events':[]}
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 (p/'global-baseline.json').write_text(json.dumps({'reason':reason,'events':s['events'],'rows':s['rows']},indent=2))
 if s['world'] is not None and ed.get_game_world()==s['world']:level.editor_request_end_play()
 print('LOCAL_MAG_LIVE_DONE',reason,len(s['rows']))
def tick(_):
 try:
  if time.monotonic()-s['start']>180:finish('timeout');return
  w=ed.get_game_world()
  if not w:
   if s['world'] is not None:finish('world ended')
   return
  if s['world'] is None:s['world']=w
  if w!=s['world']:finish('world replaced');return
  player=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(player,unreal.ProphecyAgent):return
  t=int(player.get_editor_property('tick debug'))
  if t==s['last']:return
  s['last']=t
  if not s['agents']:s['agents']=list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent))
  for threshold,value in [(20,1.)]:
   key=str(threshold)
   if t>=threshold and not s.get(key):
    for a in s['agents']:
     assert lib.set_magnetization_mode(a,value)
     assert lib.save_physical_profile_snapshot(a,'1')
    s[key]=True;s['events'].append({'tick':t,'mode':value})
  if False:
   idle=next(a for a in s['agents'] if a.get_actor_label().endswith('Agent2'))
   lib.set_magnetization_mode(idle,0);lib.save_physical_profile_snapshot(idle,'ModeTest')
   lib.set_magnetization_mode(idle,1)
   assert lib.blend_magnetization_mode_to_snapshot(idle,.5,'ModeTest',.5)
   s['hold']=True;s['events'].append({'tick':t,'hold_agent':idle.get_actor_label()})
  if t%5==0:
   for a in s['agents']:
    if not a.has_valid_agent_handle():continue
    r={'tick':t,'actor':a.get_actor_label(),'mode':lib.get_magnetization_mode(a),'attack':str(a.get_nn_attack_state()),'simulation':str(a.get_simulation_mode()),'max_speed':0.,'max_spin':0.,'max_distance_from_pelvis':0.}
    pelvis=a.get_physical_body_state('pelvis')
    if not pelvis:continue
    for bone in ['pelvis','spine_01','spine_05','head','upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r','thigh_l','calf_l','foot_l','thigh_r','calf_r','foot_r']:
     body=a.get_physical_body_state(bone)
     if not body:continue
     r['max_speed']=max(r['max_speed'],body[1].length());r['max_spin']=max(r['max_spin'],body[2].length())
     r['max_distance_from_pelvis']=max(r['max_distance_from_pelvis'],(body[0].translation-pelvis[0].translation).length())
    assert all(math.isfinite(r[k]) for k in ['mode','max_speed','max_spin','max_distance_from_pelvis']),r
    s['rows'].append(r)
  if t>=320:finish('complete')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play();print('LOCAL_MAG_LIVE_STARTED')
