import unreal,pathlib,json,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/HandEntryGate20261006'
s={'world':None,'start':time.monotonic(),'checks':[],'cases':[]}
def lib(n):return unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.'+n))
hands=lib('ProphecyAttackStartInertiaLibrary');counter=lib('ProphecyGhostAttackLibrary');debug=lib('ProphecyNNModifierDebugLibrary')
def check(b,label):
 assert b,label
 s['checks'].append(label)
def report(a):return str(debug.call_method('PrintNNModifiers',(a,)))
def count(a):return counter.call_method('GetTicksSinceLastAttack',(a,))
def configure(a,t):return hands.call_method('SetAttackStartHandInertia',(a,True,.1,.3,1.,.25,1.,1.,True,True,t))
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 (p/'live.json').write_text(json.dumps({'reason':reason,'checks':s['checks'],'cases':s['cases']},indent=2))
 if s['world'] and ed.get_game_world()==s['world']:level.editor_request_end_play()
 print('HAND_ENTRY_GATE_TEST',reason)
def tick(_):
 try:
  if time.monotonic()-s['start']>60:finish('timeout');return
  w=ed.get_game_world()
  if not w:return
  if s['world'] is None:s['world']=w
  if w!=s['world']:finish('world replaced');return
  a=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(a,unreal.ProphecyAgent) or int(a.get_editor_property('absolute tick debug'))<15:return
  for half in [False,True]:
   for ticks in [0,24,25,26,1000]:
    a.stop_nn_attack()
    check(configure(a,25),'Configure threshold25')
    check(counter.call_method('SetTicksSinceLastAttack',(a,ticks)),'Seed counter '+str(ticks))
    target=a.get_pose_reference_mesh().get_socket_location('head')+a.get_actor_forward_vector()*100
    check(a.trigger_nn_attack('slashL',target,half),'Accepted '+('half' if half else 'full')+' entry')
    r=report(a);active='Attack-start hand inertia' in r
    check(active==(ticks>25),'Strict gate '+str(ticks)+' half='+str(half))
    current=count(a);check(current==(ticks if half else 0),'Existing counter lifecycle retained')
    if active:
     check('entry ticks '+str(ticks) in r,'Captured pre-reset count shown')
     check(configure(a,9999),'Change next-entry threshold')
     check(a.trigger_nn_attack('slashL',target,half),'Retrigger accepted')
     check('Attack-start hand inertia' in report(a),'Retrigger and threshold edit preserve active effect')
    s['cases'].append({'half':half,'entry_ticks':ticks,'live_counter_after_entry':current,'active':active,'report':r})
  a.stop_nn_attack();configure(a,0)
  counter.call_method('SetTicksSinceLastAttack',(a,0));a.trigger_nn_attack('slashL',target,False)
  check('Attack-start hand inertia' not in report(a),'Default threshold0 skips zero')
  a.stop_nn_attack();counter.call_method('SetTicksSinceLastAttack',(a,1));a.trigger_nn_attack('slashL',target,False)
  check('Attack-start hand inertia' in report(a),'Default threshold0 accepts one')
  a.stop_nn_attack();finish('passed')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play();print('HAND_ENTRY_GATE_TEST_STARTED')
