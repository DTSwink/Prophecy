import unreal,builtins,time,json,pathlib,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyAttackCheckpointLibrary'))
current=unreal.ProphecyAttackCheckpoint.CURRENT174664
alternative=unreal.ProphecyAttackCheckpoint.PREDICTIVE_PIN160664
s=dict(start=time.monotonic(),phase=0,rows=[],last=-1,agents=[],ticks=0)
builtins._attack_checkpoint_test=s
def selection(a):
 return lib.call_method('GetAttackCheckpoint',(a,))
def set_cp(a,v):
 result=lib.call_method('SetAttackCheckpoint',(a,v))
 # UE hides a boolean ReturnValue for functions with output parameters: None
 # indicates failure, otherwise the sole output is the error string.
 assert result is not None and str(result)=='',str(result)
def target(a):return a.get_actor_location()+unreal.Vector(0,80,40)
def start_attack(a,half=False):assert a.trigger_nn_attack('jabL',target(a),half,None)
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/AttackCheckpointSelection.json').write_text(json.dumps(dict(reason=reason,rows=s['rows']),default=str,indent=2))
 if ed.get_game_world():unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
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
   if len(agents)<3 or t<.25:return
   s['agents']=agents[:3]
   for a in agents:
    a.set_actor_tick_enabled(False)
    a.stop_nn_attack()
   for a in s['agents']:assert selection(a)==(current,current,False),str(selection(a))
   set_cp(s['agents'][0],alternative)
   for a in s['agents']:start_attack(a)
   assert selection(s['agents'][0])==(alternative,alternative,True)
   assert selection(s['agents'][1])==(current,current,True)
   s['phase']=1;s['phase_tick']=s['ticks']
  elif s['phase']==1 and s['ticks']-s['phase_tick']>=4:
   a=s['agents'][0];b=s['agents'][1]
   before=[x.get_nn_attack_state() for x in (a,b)]
   assert all(x is not None and x[-1]>0 for x in before),str(before)
   set_cp(a,current);set_cp(b,alternative)
   assert [x.get_nn_attack_state() for x in (a,b)]==before,'Setter reset attack state'
   assert selection(a)==(current,alternative,True)
   assert selection(b)==(alternative,current,True)
   # Existing retrigger semantics: target/type update keeps model and latches.
   assert a.trigger_nn_attack('jabR',target(a),False,None)
   after=a.get_nn_attack_state()
   assert after[1:]==before[0][1:],str((before,after))
   s['rows'].append(dict(case='queued_selection_and_retrigger',before=before,after=after,selection=[selection(x) for x in s['agents']]))
   s['phase']=2;s['phase_tick']=s['ticks']
  elif s['phase']==2 and s['ticks']-s['phase_tick']>=4:
   for a in s['agents']:a.stop_nn_attack()
   set_cp(s['agents'][2],alternative)
   for i,a in enumerate(s['agents']):start_attack(a,i==2)
   assert selection(s['agents'][0])==(current,current,True)
   assert selection(s['agents'][1])==(alternative,alternative,True)
   assert selection(s['agents'][2])==(alternative,alternative,True)
   s['phase']=3;s['phase_tick']=s['ticks']
  elif s['phase']==3 and s['ticks']-s['phase_tick']>=6:
   states=[a.get_nn_attack_state() for a in s['agents']]
   assert all(x is not None and x[-1]>0 for x in states),str(states)
   s['rows'].append(dict(case='opposite_batch_sizes_and_half_attack',states=states,selection=[selection(x) for x in s['agents']]))
   for a in s['agents']:a.stop_nn_attack();set_cp(a,current)
   assert all(selection(a)==(current,current,False) for a in s['agents'])
   finish('passed')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
