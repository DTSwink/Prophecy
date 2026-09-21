import unreal,json,pathlib,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world()
s={'start':time.monotonic(),'rows':[]}
def state(a):
 x=a.get_nn_attack_state();d=unreal.ProphecyNNDefenseLibrary.get_nn_defense_status(a)
 return {'name':a.get_name(),'attack':[str(x[0])]+list(x[1:]) if x else None,'activity':str(unreal.ProphecyNNDefenseLibrary.get_agent_state(a)),'defense':dict(active=d.active,steps=d.completed_steps,frame=d.attacker_frame,contact=str(d.contact_collider),harmful=d.harmful_contact,blocked=d.blocked) if d else None}
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb']);level.editor_request_end_play()
 p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/DodgeHitDelay/PIE.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps({'error':error,'rows':s['rows']},separators=(',',':')))
 print('COMBAT_REVERSE_CAPTURE',len(s['rows']),error)
def tick(dt):
 try:
  w=ed.get_game_world()
  if not w:return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if time.monotonic()-s['start']>120:raise RuntimeError('timeout')
  if 'p' not in s:
   p=next((a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent) if a.is_player_controlled() and a.has_valid_agent_handle()),None)
   if not p:return
   o=p.get_editor_property('CombatDemoOpponent')
   if not o or not o.has_valid_agent_handle():return
   s.update(p=p,o=o)
  p,o=s['p'],s['o'];reverse=False;dodge=True
  lib=unreal.get_default_object(unreal.ProphecyNNDefenseLibrary)
  delay=1 if t<3.8 else 0 if t<6.8 else 3
  if 'delay' not in s:
   assert lib.call_method('GetDodgeFramesAfterHit',(o,))==1
   assert not lib.call_method('SetDodgeFramesAfterHit',(o,-1))
  if s.get('delay')!=delay:
   assert lib.call_method('SetDodgeFramesAfterHit',(o,delay))
   assert lib.call_method('GetDodgeFramesAfterHit',(o,))==delay
   assert lib.call_method('GetDodgeFramesAfterHit',(p,))==1
   s['delay']=delay
  p.set_editor_property('CombatDemoReverseRoles',reverse);p.set_editor_property('CombatDemoUseDodge',dodge)
  s['rows'].append(dict(t=t,reverse=reverse,dodge=dodge,delay=delay,player=state(p),opponent=state(o)))
  if t>=8.8:finish()
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
