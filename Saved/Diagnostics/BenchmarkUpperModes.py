import unreal,pathlib,json,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
folder=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/AttackPerformance')
asset=unreal.load_asset('/Game/_mygame/Tests/SlashChain30/AS_SlashChain30_Reference')
assert asset
s=dict(start=time.monotonic(),last=None,n=0,events=[])
cases=['clip','checkpoint','checkpoint','clip']
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 w=ed.get_game_world()
 if w:unreal.SystemLibrary.execute_console_command(w,'Prophecy.AttackPerf.Capture stop')
 (folder/'upper_modes_meta.json').write_text(json.dumps(dict(error=error,asset=asset.get_path_name(),events=s['events']),indent=2))
 if w:level.editor_request_end_play()
 print('UPPER_BENCHMARK_DONE',error or 'complete')
def tick(dt):
 try:
  assert time.monotonic()-s['start']<100,'Timeout'
  w=ed.get_game_world()
  if not w:return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t;s['n']+=1;n=s['n']
  a=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(a,unreal.ProphecyAgent):return
  if n==20:
   for x in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
    x.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC);x.set_actor_tick_enabled(False);x.stop_nn_attack()
    if x!=a:x.set_editor_property('bNNInferenceEnabled',False)
   a.set_locomotion_policy_blend_times(0.,0.)
   a.set_locomotion_input(unreal.Vector(0,1,0),True,unreal.Vector(0,1,0),.4,1.)
   unreal.get_default_object(unreal.ProphecyGhostAttackLibrary).call_method('SetAttackArmedBlocked',(a,True))
  case=(n-40)//220;off=(n-40)%220
  if 0<=case<len(cases):
   mode=cases[case]
   if off==0:
    a.stop_nn_attack();a.stop_nn_animation_layer(0.)
    if mode=='clip':assert a.play_nn_animation_layer(asset,'spine_01',0.,0.,1.,True),'Clip rejected'
    else:
     unreal.get_default_object(unreal.ProphecyGhostAttackLibrary).call_method('SetAttackArmedBlocked',(a,True))
     names,p,_,_=a.read_nn_future_world_pose();pelvis=p[[str(b) for b in names].index('pelvis')].translation
     assert a.trigger_nn_attack('slashR',pelvis+unreal.Vector(0,180,10),True,None)
    s['events'].append(dict(case=case,mode=mode,frame=n))
   if off==40:unreal.SystemLibrary.execute_console_command(w,'Prophecy.AttackPerf.Capture upper_'+mode+'_'+str(case)+' 160')
   if mode=='checkpoint' and off>=40:assert a.get_nn_attack_state(),'Half attack unexpectedly ended'
  if n>=921:finish()
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
print('UPPER_BENCHMARK_STARTED')
