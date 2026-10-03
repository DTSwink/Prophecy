import unreal,builtins,time,json,pathlib,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyAttackCheckpointLibrary'))
cp=unreal.ProphecyAttackCheckpoint
choices=[cp.CURRENT174664,cp.PREDICTIVE_PIN160664,cp.PREDICTIVE_PIN184064]
good=cp.SEPTEMBER20_GOOD265458
s=dict(start=time.monotonic(),phase=0,rows=[],last=-1,agents=[],ticks=0)
builtins._forced_good_kicks=s
def selection(a):return lib.call_method('GetAttackCheckpoint',(a,))
def choose(a,v):
 result=lib.call_method('SetAttackCheckpoint',(a,v));assert result is not None and str(result)=='',str(result)
def trigger(a,name):
 assert a.trigger_nn_attack(name,a.get_actor_location()+unreal.Vector(0,80,40),False,None)
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/ForcedGoodKicks-result.json').write_text(json.dumps(dict(reason=reason,rows=s['rows']),default=str,indent=2))
 print('FORCED_GOOD_KICKS',reason)
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
   if len(agents)<3 or t<.6:return
   s['agents']=agents[:3]
   for a in agents:a.set_actor_tick_enabled(False);a.stop_nn_attack()
   for i,a in enumerate(s['agents']):
    choose(a,choices[i]);trigger(a,'kickL' if i!=1 else 'kickR')
    assert selection(a)==(choices[i],good,True),str(selection(a))
   s['phase']=1;s['phase_tick']=s['ticks']
  elif s['phase']==1 and s['ticks']-s['phase_tick']>=6:
   states=[a.get_nn_attack_state() for a in s['agents']]
   assert all(x is not None and x[-1]>0 for x in states),str(states)
   s['rows'].append(dict(case='both_kicks_ignore_three_agent_choices',states=states,selection=[selection(a) for a in s['agents']]))
   a=s['agents'][0];choose(a,choices[1]);before=a.get_nn_attack_state();trigger(a,'kickR')
   assert a.get_nn_attack_state()[1:]==before[1:],'Kick retarget reset phase'
   assert selection(a)==(choices[1],good,True)
   trigger(a,'jabR')
   assert a.get_nn_attack_state()[1:]==before[1:],'Kick to melee reset phase'
   assert selection(a)==(choices[1],choices[1],True)
   s['rows'].append(dict(case='kick_exit_uses_selected_without_restart',before=before,after=a.get_nn_attack_state(),selection=selection(a)))
   s['phase']=2;s['phase_tick']=s['ticks']
  elif s['phase']==2 and s['ticks']-s['phase_tick']>=6:
   for i,a in enumerate(s['agents']):
    a.stop_nn_attack();choose(a,choices[i]);trigger(a,['jabL','overR','slashR'][i])
    assert selection(a)==(choices[i],choices[i],True),str(selection(a))
   s['phase']=3;s['phase_tick']=s['ticks']
  elif s['phase']==3 and s['ticks']-s['phase_tick']>=6:
   states=[a.get_nn_attack_state() for a in s['agents']]
   assert all(x is not None and x[-1]>0 for x in states),str(states)
   s['rows'].append(dict(case='other_attacks_use_independent_choices',states=states,selection=[selection(a) for a in s['agents']]))
   a=s['agents'][0];before=a.get_nn_attack_state();choose(a,choices[2]);trigger(a,'overL')
   assert selection(a)==(choices[2],choices[0],True),'Non-kick retarget lost active checkpoint latch'
   trigger(a,'kickR');assert selection(a)==(choices[2],good,True)
   assert a.get_nn_attack_state()[1:]==before[1:],'Melee to kick reset phase'
   trigger(a,'jabR');assert selection(a)==(choices[2],choices[2],True)
   assert a.get_nn_attack_state()[1:]==before[1:],'Kick to selected reset phase'
   s['rows'].append(dict(case='cross_family_round_trip_keeps_latches',before=before,after=a.get_nn_attack_state(),selection=selection(a)))
   for a in s['agents']:a.stop_nn_attack();choose(a,choices[0]);assert selection(a)==(choices[0],choices[0],False)
   finish('passed')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('FORCED_GOOD_KICKS_STARTED')
