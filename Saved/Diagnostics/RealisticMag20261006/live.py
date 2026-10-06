import unreal,json,pathlib,time,traceback,math
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RealisticMag20261006'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
lib=unreal.ProphecyPhysicalProfileLibrary
s={'world':None,'start':time.monotonic(),'last':None,'agents':[],'rows':[],'events':[]}
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 (p/'live.json').write_text(json.dumps({'reason':reason,'events':s['events'],'rows':s['rows']},indent=2))
 if s['world'] is not None and ed.get_game_world()==s['world']:level.editor_request_end_play()
 print('BONE_MODE_REALISTIC_LIVE_DONE',reason,len(s['rows']))
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
  if t>=20 and not s.get('mixed'):
   for a in s['agents']:
    assert not a.is_realistic_mode_active()
    assert lib.set_magnetization_mode(a,1)
    assert lib.set_magnetization_mode_below(a,'upperarm_r',0,True)==3
    assert lib.set_body_magnetization_mode(a,'head',.2)
    assert lib.set_body_magnetization_mode(a,'lowerarm_l',.8)
    assert lib.save_physical_profile_snapshot(a,'1')
   s['mixed']=True;s['events'].append({'tick':t,'mixed':True})
  if t>=80 and not s.get('threshold'):
   a=next(a for a in s['agents'] if a.get_actor_label().endswith('Agent2'))
   cap=a.get_agent_capsule();r=cap.get_scaled_capsule_radius();hh=cap.get_scaled_capsule_half_height()
   bottom=cap.get_world_location().z-r-(hh-r)*abs(cap.get_up_vector().z)
   h=min(a.get_physical_body_state(b)[0].translation.z for b in ['foot_l','foot_r'])-bottom
   assert h>.5,('Need positive measurable idle foot height',h)
   modes={b:lib.get_body_magnetization_mode(a,b) for b in ['head','hand_l','hand_r']}
   strength=float(a.get_editor_property('world_magnetization_linear_strength_scale'))
   assert a.set_realistic_mode(True,h+.5) and not a.is_realistic_mode_active()
   assert a.set_realistic_mode(True,h-.5) and a.is_realistic_mode_active()
   assert a.set_realistic_mode(True,h+.5) and not a.is_realistic_mode_active()
   assert a.set_realistic_mode(True,h-.5) and a.is_realistic_mode_active()
   assert a.set_realistic_mode(False,h-.5) and not a.is_realistic_mode_active()
   assert modes=={b:lib.get_body_magnetization_mode(a,b) for b in modes}
   assert strength==float(a.get_editor_property('world_magnetization_linear_strength_scale'))
   s['threshold']=True;s['events'].append({'tick':t,'threshold_crossings':4,'height_cm':h,'mode_strength_unchanged':True})
  if t>=300 and not s.get('return'):
   a=next(a for a in s['agents'] if a.get_actor_label().endswith('Agent2'))
   assert lib.set_body_magnetization_mode(a,'hand_r',.7)
   assert lib.blend_body_magnetization_mode_to_snapshot(a,'hand_r',.5,'1',.5)
   s['return']=True
  if t>=450 and not s.get('uniform'):
   for a in s['agents']:
    lib.set_magnetization_mode(a,1);lib.save_physical_profile_snapshot(a,'1')
   s['uniform']=True
  if t>=650 and not s.get('mixed_again'):
   for a in s['agents']:
    assert lib.set_magnetization_mode_below(a,'upperarm_r',.25,False)==2
    lib.save_physical_profile_snapshot(a,'1')
   s['mixed_again']=True
  if t%5==0:
   for a in s['agents']:
    if not a.has_valid_agent_handle():continue
    pelvis=a.get_physical_body_state('pelvis')
    if not pelvis:continue
    row={'tick':t,'actor':a.get_actor_label(),'active':a.is_realistic_mode_active(),'modes':{b:lib.get_body_magnetization_mode(a,b) for b in ['head','upperarm_r','lowerarm_r','hand_r','lowerarm_l','hand_l']},'max_span':0.}
    for b in ['head','hand_l','hand_r','foot_l','foot_r']:
     body=a.get_physical_body_state(b)
     if body:row['max_span']=max(row['max_span'],(body[0].translation-pelvis[0].translation).length())
    s['rows'].append(row);assert math.isfinite(row['max_span']) and row['max_span']<180,row
  if t>=900:finish('complete')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play();print('BONE_MODE_REALISTIC_LIVE_STARTED')