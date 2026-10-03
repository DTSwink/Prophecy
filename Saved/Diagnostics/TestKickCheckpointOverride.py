import unreal,builtins,pathlib,json,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyAttackCheckpointLibrary'))
enum=unreal.get_type_from_enum(unreal.load_object(None,'/Script/GameAnimationSample3.EProphecyAttackCheckpoint'))
choices=list(enum)
old=next(x for x in choices if 'SEPTEMBER20' in str(x))
selected=next(x for x in choices if 'PIN184064' in str(x))
s=dict(wall=time.monotonic(),done=False)
builtins._kick_override_test=s
def finish(reason):
 if s['done']:return
 s['done']=True
 unreal.unregister_slate_post_tick_callback(s['cb'])
 pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/KickCheckpointOverride.json').write_text(json.dumps(dict(result=reason)))
 if ed.get_game_world():unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
 print('KICK_OVERRIDE_TEST',reason)
def tick(_):
 try:
  w=ed.get_game_world()
  if not w or unreal.GameplayStatics.get_time_seconds(w)<.8:
   if time.monotonic()-s['wall']>60:finish('Timeout')
   return
  agents=list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent))
  assert len(agents)>=2
  a,b=agents[:2]
  for x in (a,b):
   x.stop_nn_attack()
   lib.call_method('SetAttackCheckpoint',(x,selected))
  def read(x):return lib.call_method('GetAttackCheckpoint',(x,))
  def start(x,family):
   assert x.trigger_nn_attack(family,x.get_actor_location()+unreal.Vector(100,120,40),False,None)
  def toggle(x,v):assert lib.call_method('SetKickCheckpointOverride',(x,v))
  for family in ('kickL','kickR'):
   for x in (a,b):
    x.stop_nn_attack();start(x,family);assert read(x)==(selected,selected,True),str(read(x))
  a.stop_nn_attack();toggle(a,True);start(a,'kickL')
  assert read(a)==(selected,old,True)
  assert read(b)==(selected,selected,True),'Override leaked to another agent'
  state=a.get_nn_attack_state();toggle(a,False)
  assert a.get_nn_attack_state()==state and read(a)==(selected,old,True),'Toggle changed ongoing attack'
  a.stop_nn_attack();start(a,'kickR');assert read(a)==(selected,selected,True)
  a.stop_nn_attack();toggle(a,True);start(a,'hookL');assert read(a)==(selected,selected,True)
  state=a.get_nn_attack_state();start(a,'kickR')
  assert read(a)==(selected,old,True) and a.get_nn_attack_state()[1:]==state[1:]
  start(a,'overL');assert read(a)==(selected,selected,True)
  toggle(a,False)
  a.stop_nn_attack();start(a,'kickL');assert read(a)==(selected,selected,True)
  finish('passed: both kicks default selected, per-agent opt-in, toggle preserves ongoing state, fresh entry and family changes route correctly')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
