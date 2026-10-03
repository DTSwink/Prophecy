import unreal,builtins,time,json,pathlib,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyAttackCheckpointLibrary'))
choices=[unreal.ProphecyAttackCheckpoint.CURRENT174664,unreal.ProphecyAttackCheckpoint.PREDICTIVE_PIN160664,unreal.ProphecyAttackCheckpoint.PREDICTIVE_PIN184064]
s=dict(start=time.monotonic(),phase=0,rows=[],last=-1,agents=[],ticks=0)
builtins._attack184064_test=s
def selection(a):return lib.call_method('GetAttackCheckpoint',(a,))
def set_cp(a,v):
 result=lib.call_method('SetAttackCheckpoint',(a,v))
 assert result is not None and str(result)=='',str(result)
def start(a,half=False,attack='jabL'):
 assert a.trigger_nn_attack(attack,a.get_actor_location()+a.get_actor_forward_vector()*100+unreal.Vector(0,0,70),half,None)
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/Attack184064Selection.json').write_text(json.dumps(dict(reason=reason,rows=s['rows']),default=str,indent=2))
 if ed.get_game_world():unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
 s['agents'].clear()
def tick(_):
 try:
  if time.monotonic()-s['start']>90:finish('timeout');return
  w=ed.get_game_world()
  if not w:return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t;s['ticks']+=1
  if s['phase']==0:
   agents=list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent))
   if len(agents)<3 or t<.75:return
   s['agents']=agents[:3]
   for a in agents:a.set_actor_tick_enabled(False);a.stop_nn_attack()
   for a,c in zip(s['agents'],choices):set_cp(a,c);start(a)
   assert [selection(a) for a in s['agents']]==[(c,c,True) for c in choices]
   s['phase']=1;s['phase_tick']=s['ticks']
  elif s['ticks']-s['phase_tick']>=4:
   agents=s['agents'];phase=s['phase'];states=[a.get_nn_attack_state() for a in agents]
   assert all(x is not None and x[-1]>0 for x in states),str(states)
   s['rows'].append(dict(phase=phase,states=states,selections=[selection(a) for a in agents]))
   if phase==1:
    s['next']=[choices[2],choices[0],choices[1]]
    for a,c in zip(agents,s['next']):set_cp(a,c)
    assert [a.get_nn_attack_state() for a in agents]==states,'Selection reset running state'
    assert [selection(a) for a in agents]==[(c,e,True) for c,e in zip(s['next'],choices)]
    for a in agents:
     old=a.get_nn_attack_state()
     assert a.trigger_nn_attack('jabR',a.get_actor_location()+unreal.Vector(100,0,70),False,None)
     assert a.get_nn_attack_state()[1:]==old[1:],'Retrigger reset phase/frame'
   elif phase==2:
    for i,a in enumerate(agents):a.stop_nn_attack();start(a,i==0)
    assert [selection(a) for a in agents]==[(c,c,True) for c in s['next']]
   elif phase==3:
    for i,a in enumerate(agents):a.stop_nn_attack();set_cp(a,choices[2]);start(a,i==0,'headbutt')
    assert all(selection(a)==(choices[2],choices[2],True) for a in agents)
   elif phase==4:
    for a in agents:a.stop_nn_attack();set_cp(a,choices[0]);start(a)
    assert all(selection(a)==(choices[0],choices[0],True) for a in agents)
   else:
    for a in agents:a.stop_nn_attack();set_cp(a,choices[0])
    assert all(selection(a)==(choices[0],choices[0],False) for a in agents)
    finish('passed');return
   s['phase']+=1;s['phase_tick']=s['ticks']
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
