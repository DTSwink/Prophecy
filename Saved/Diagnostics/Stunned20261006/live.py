import unreal,json,pathlib,time,traceback
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/Stunned20261006'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
s={'world':None,'start':time.monotonic(),'last':None,'events':[],'rows':[],'a':None,'b':None,'rearm':False,'cross':False,'paused':False}
@unreal.uclass()
class StunExpiryProbe(unreal.ProphecyAgent):
 @unreal.ufunction(override=True)
 def on_stunned_ended(self):
  s['events'].append({'actor':self.get_name(),'active_at_event':self.is_stunned(),'last_observed_tick':s['last']})
  if s['rearm']:
   s['rearm']=False;assert self.start_stunned(.1)
  if s['cross']:
   s['cross']=False
   other=s['b'] if self==s['a'] else s['a'];assert other.start_stunned(.1)
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 (p/'live.json').write_text(json.dumps({'reason':reason,'events':s['events'],'rows':s['rows'],'pause_verified':s.get('pause_verified',False)},indent=2))
 if s['world'] is not None and ed.get_game_world()==s['world']:
  if s['paused']:unreal.GameplayStatics.set_game_paused(s['world'],False)
  level.editor_request_end_play()
 print('STUN_LIVE_DONE',reason)
def spawn(w,x):
 tr=unreal.Transform(location=unreal.Vector(x,10000,200));gs=unreal.get_default_object(unreal.GameplayStatics)
 a=gs.call_method('BeginDeferredActorSpawnFromClass',args=(w,StunExpiryProbe,tr,unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN,None,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
 a.set_editor_property('auto_initialize_agent_runtime',False);a.set_editor_property('auto_ensure_standalone_nn_manager',False)
 gs.call_method('FinishSpawningActor',args=(a,tr,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
 assert not a.is_actor_tick_enabled();assert not a.is_stunned()
 a.set_editor_property('custom_time_dilation',.1)
 return a
def tick(_):
 try:
  if time.monotonic()-s['start']>90:finish('timeout');return
  w=ed.get_game_world()
  if not w:return
  if s['world'] is None:s['world']=w
  if w!=s['world']:finish('world replaced');return
  if s['paused']:
   assert s['a'].is_stunned() and len(s['events'])==3
   if time.monotonic()-s['pause_start']>.5:
    assert unreal.GameplayStatics.set_game_paused(w,False)
    s['paused']=False;s['pause_verified']=True
   return
  player=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(player,unreal.ProphecyAgent):return
  t=int(player.get_editor_property('tick debug'))
  if t==s['last']:return
  s['last']=t
  if t>=5 and s['a'] is None:
   s['a']=spawn(w,10000);s['b']=spawn(w,10500);s['begin']=t
   assert s['a'].start_stunned(1)
  a=s['a'];b=s['b']
  if a is None:return
  n=t-s['begin'];count=len(s['events'])
  if n==30:
   assert a.is_stunned() and count==0
   assert a.start_stunned(.1)
  if n==35:assert a.is_stunned() and count==0
  if n==36:
   assert not a.is_stunned() and count==1
   s['rearm']=True;assert a.start_stunned(.1)
  if n==42:assert a.is_stunned() and count==2
  if n==48:
   assert not a.is_stunned() and count==3
   assert a.start_stunned(1);a.disable_stunned()
  if n==60:
   assert not a.is_stunned() and count==3
   assert a.start_stunned(.1)
   assert unreal.GameplayStatics.set_game_paused(w,True)
   s['paused']=True;s['pause_start']=time.monotonic()
  if n==65:assert a.is_stunned() and count==3
  if n==66:
   assert not a.is_stunned() and count==4
   assert a.start_stunned(0) and not a.is_stunned() and len(s['events'])==5
   assert a.start_stunned(.1)
  if n==69:a.disable_stunned()
  if n==75:
   assert not a.is_stunned() and count==5
   s['cross']=True;assert a.start_stunned(.1);assert b.start_stunned(.1)
  if n==81:assert count==6 and a.is_stunned()!=b.is_stunned()
  if n==87:
   assert count==7 and not a.is_stunned() and not b.is_stunned()
   assert b.start_stunned(.1);b.destroy_actor()
  s['rows'].append({'tick':n,'active':a.is_stunned(),'events':len(s['events'])})
  if n>=95:
   assert len(s['events'])==7 and not any(e['active_at_event'] for e in s['events'])
   assert s['pause_verified'] and not a.is_actor_tick_enabled()
   finish('complete')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play();print('STUN_LIVE_STARTED')
