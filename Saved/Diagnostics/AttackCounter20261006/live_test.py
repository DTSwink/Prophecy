import unreal,pathlib,time,json,traceback
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/AttackCounter20261006'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
s={'world':None,'last':None,'frame':0,'start':time.monotonic(),'checks':[]}
families=['slashL','slashR','slashLU','slashRU','slashLD','slashRD','pike','jabL','jabR','hookL','hookR','overL','overR','headbutt','kickL','kickR']
def check(label,passed,**data):
 s['checks'].append(dict(check=label,passed=bool(passed),**data));assert passed,(label,data)
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 (p/'live-test.json').write_text(json.dumps(dict(reason=reason,checks=s['checks']),indent=2))
 if s['world'] is not None and ed.get_game_world()==s['world']:level.editor_request_end_play()
 print('ATTACK_COUNTER_DONE',reason)
def tick(dt):
 try:
  if time.monotonic()-s['start']>90:finish('timeout');return
  w=ed.get_game_world()
  if w is None:return
  if s['world'] is None:s['world']=w
  if w!=s['world']:finish('world replaced');return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t;s['frame']+=1;f=s['frame']
  if f==5:
   s['agents']=list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent))
   for a in s['agents']:a.set_actor_tick_enabled(False)
  if f==20:
   agents=[a for a in s['agents'] if a.has_valid_agent_handle()]
   check('two registered agents',len(agents)>=2)
   a=unreal.GameplayStatics.get_player_pawn(w,0);b=next(x for x in agents if x!=a)
   s['a']=a;s['b']=b
   check('new agents start zero',a.get_attack_counter()==0 and b.get_attack_counter()==0)
   init=unreal.ProphecyAgentResetLibrary.initialize_agent_reset(w)
   check('reset snapshot available',init is not None,result=str(init))
   names,pose,_,_=a.read_nn_future_world_pose();target=pose[[str(n) for n in names].index('pelvis')].translation+unreal.Vector(-30,90,30)
   for i,name in enumerate(families,1):
    a.stop_nn_attack();before=a.get_attack_counter()
    check('stop retains number',before==i-1,family=name,counter=before)
    check('valid attack starts',a.trigger_nn_attack(name,target,False),family=name)
    check('accepted entry increments once',a.get_attack_counter()==i,family=name,counter=a.get_attack_counter())
    check('repeat trigger succeeds',a.trigger_nn_attack(name,target,False),family=name)
    check('repeat trigger retains number',a.get_attack_counter()==i,family=name)
    check('invalid attack rejected',not a.trigger_nn_attack('invalid_attack_counter_test',target,False),family=name)
    check('failure retains number',a.get_attack_counter()==i,family=name)
    if not name.startswith('kick'):
     check('half transition succeeds',a.set_nn_half_attack_enabled(True),family=name)
     check('half transition retains number',a.get_attack_counter()==i,family=name)
     check('full transition succeeds',a.set_nn_half_attack_enabled(False),family=name)
     check('full transition retains number',a.get_attack_counter()==i,family=name)
   check('other agent independent',b.get_attack_counter()==0)
   names,pose,_,_=b.read_nn_future_world_pose();bt=pose[[str(n) for n in names].index('pelvis')].translation+unreal.Vector(30,90,30)
   check('other agent attack starts',b.trigger_nn_attack('jabR',bt,True))
   check('independent sequence',a.get_attack_counter()==16 and b.get_attack_counter()==1)
   s['counts']={x.get_name():x.get_attack_counter() for x in agents}
  if 21<=f<=24:
   check('no increment per tick',s['a'].get_attack_counter()==16 and s['b'].get_attack_counter()==1,frame=f)
  if f==25:
   reset=unreal.ProphecyAgentResetLibrary.reset_initial_agents(w)
   check('reset accepted',reset is not None,result=str(reset))
  if f==30:
   check('reset completed',not s['a'].get_nn_attack_state() and not s['b'].get_nn_attack_state())
   check('reset keeps attack numbers',s['a'].get_attack_counter()==16 and s['b'].get_attack_counter()==1)
   a=s['a'];names,pose,_,_=a.read_nn_future_world_pose();target=pose[[str(n) for n in names].index('pelvis')].translation+unreal.Vector(-30,90,30)
   check('attack after reset starts',a.trigger_nn_attack('jabL',target,True))
   check('attack after reset gets fresh number',a.get_attack_counter()==17)
   check('retarget family succeeds',a.trigger_nn_attack('hookL',target,True))
   check('retarget keeps ongoing number',a.get_attack_counter()==17)
   finish('complete')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play();print('ATTACK_COUNTER_STARTED')
