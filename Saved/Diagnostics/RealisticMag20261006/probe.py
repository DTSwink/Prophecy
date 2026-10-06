import unreal,json,pathlib,time,traceback
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RealisticMag20261006'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
lib=unreal.ProphecyPhysicalProfileLibrary
s={'world':None,'start':time.monotonic(),'last':None,'rows':[],'events':[],'a':None}
@unreal.uclass()
class RealisticEventProbe(unreal.ProphecyAgent):
 @unreal.ufunction(override=True)
 def on_start_realistic(self):s['events'].append('start')
 @unreal.ufunction(override=True)
 def on_end_realistic(self):s['events'].append('end')
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 (p/'probe.json').write_text(json.dumps({'reason':reason,'events':s['events'],'rows':s['rows']},indent=2))
 if s['world'] is not None and ed.get_game_world()==s['world']:level.editor_request_end_play()
 print('REALISTIC_NATIVE_PROBE_DONE',reason)
def tick(_):
 try:
  if time.monotonic()-s['start']>90:finish('timeout');return
  w=ed.get_game_world()
  if not w:return
  if s['world'] is None:s['world']=w
  if w!=s['world']:finish('world changed');return
  player=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(player,unreal.ProphecyAgent):return
  t=int(player.get_editor_property('tick debug'))
  if t==s['last']:return
  s['last']=t
  if t>=20 and s['a'] is None:
   tr=unreal.Transform(location=unreal.Vector(10000,10000,200))
   gs=unreal.get_default_object(unreal.GameplayStatics)
   a=gs.call_method('BeginDeferredActorSpawnFromClass',args=(w,RealisticEventProbe,tr,unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN,None,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
   s['a']=a
   a.set_editor_property('auto_initialize_agent_runtime',False);a.set_editor_property('auto_ensure_standalone_nn_manager',False)
   a.get_agent_mesh().set_skeletal_mesh_asset(unreal.load_asset('/Game/_mygame/SKM_UEFN_Mannequin'))
   gs.call_method('FinishSpawningActor',args=(a,tr,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
   a.set_actor_tick_enabled(True)
   lib.set_magnetization_mode(a,1);lib.set_body_magnetization_mode(a,'hand_r',0);lib.save_physical_profile_snapshot(a,'1')
   lib.set_body_magnetization_mode(a,'hand_r',.7)
   assert lib.blend_body_magnetization_mode_to_snapshot(a,'hand_r',.5,'1',.5)
   s['begin']=t
  a=s['a']
  if a is None:return
  n=t-s['begin']
  if n==5:
   cap=a.get_agent_capsule();bottom=cap.get_world_location().z-cap.get_scaled_capsule_half_height()
   h=min(a.get_agent_mesh().get_socket_location(b).z for b in ['foot_l','foot_r'])-bottom
   assert h>.5,h
   assert a.set_realistic_mode(True,h+.5) and not a.is_realistic_mode_active()
   assert a.set_realistic_mode(True,h-.5) and a.is_realistic_mode_active()
   assert a.set_realistic_mode(True,h-.5) and a.is_realistic_mode_active()
   assert a.set_realistic_mode(True,h+.5) and not a.is_realistic_mode_active()
   assert a.set_realistic_mode(True,h-.5) and a.is_realistic_mode_active()
   assert a.set_realistic_mode(False,h-.5) and not a.is_realistic_mode_active()
   assert s['events']==['start','end','start','end'],s['events']
  s['rows'].append({'tick':n,'hand_r':lib.get_body_magnetization_mode(a,'hand_r'),'hand_l':lib.get_body_magnetization_mode(a,'hand_l')})
  if n>=65:
   for frame,want in [(30,.7),(45,.35),(60,0)]:
    r=next(r for r in s['rows'] if r['tick']==frame)
    assert abs(r['hand_r']-want)<.002,(frame,r,want)
   assert all(r['hand_l']==1 for r in s['rows'])
   assert s['events']==['start','end','start','end'],s['events']
   finish('complete')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play();print('REALISTIC_NATIVE_PROBE_STARTED')
