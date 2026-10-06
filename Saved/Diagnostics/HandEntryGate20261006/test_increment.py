import unreal,pathlib,json,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/HandEntryGate20261006'
w=ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.LiveAgentTypes Inspect')
r=(p.parent/'LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
if 'native_properties=0 pin_types=0' not in r:
 unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.LiveAgentTypes Repair')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RepairLibraryDefaults')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.LiveAgentTypes Inspect')
r=(p.parent/'LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
assert 'native_properties=0 pin_types=0 status=3' in r,r
(p/'increment-types.txt').write_text(r)
s={'world':None,'start':time.monotonic(),'checks':[]}
counter=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyGhostAttackLibrary'))
system=unreal.get_default_object(unreal.SystemLibrary)
def check(b,label):
 assert b,label
 s['checks'].append(label)
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 (p/'increment.json').write_text(json.dumps({'reason':reason,'checks':s['checks']},indent=2))
 if s['world'] and ed.get_game_world()==s['world']:level.editor_request_end_play()
 print('INCREMENT_TEST',reason)
def tick(_):
 try:
  if time.monotonic()-s['start']>60:finish('timeout');return
  w=ed.get_game_world()
  if not w:return
  if s['world'] is None:s['world']=w
  if w!=s['world']:finish('world replaced');return
  a=unreal.GameplayStatics.get_player_pawn(w,0)
  if not a or int(a.get_editor_property('absolute tick debug'))<15:return
  others=[x for x in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent) if x!=a]
  before=[x.get_attack_counter() for x in others]
  a.stop_nn_attack()
  counter.call_method('SetTicksSinceLastAttack',(a,123))
  system.call_method('SetInt64PropertyByName',(a,'AttackCounter',9998))
  for expected in [9999,0,1]:
   check(a.call_method('IncrementAttackCounter',())==expected,'Manual return '+str(expected))
   check(a.get_attack_counter()==expected,'Getter '+str(expected))
  check(counter.call_method('GetTicksSinceLastAttack',(a,))==123,'Ticks since last attack unchanged')
  target=a.get_pose_reference_mesh().get_socket_location('head')+a.get_actor_forward_vector()*100
  check(a.trigger_nn_attack('slashL',target,True),'Accepted new attack')
  check(a.get_attack_counter()==2,'Automatic entry still increments once')
  state=a.get_nn_attack_state()
  check(a.call_method('IncrementAttackCounter',())==3,'Manual increment during active attack')
  check(a.get_nn_attack_state()==state,'Manual increment preserves attack state')
  check(a.trigger_nn_attack('slashL',target,True),'Accepted retrigger')
  check(a.get_attack_counter()==3,'Retrigger preserves manual count')
  check([x.get_attack_counter() for x in others]==before,'Other agents unchanged')
  a.stop_nn_attack();finish('passed')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play();print('INCREMENT_TEST_STARTED')
