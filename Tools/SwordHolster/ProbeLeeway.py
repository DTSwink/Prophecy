"""Owned PIE visual smoke test; reads existing S, never edits/saves user assets."""
import json, pathlib, time, traceback, unreal
root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/SheathingLeeway20261012'
out.mkdir(parents=True,exist_ok=True)
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Existing Play left untouched'
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySwordHolsterLibrary'))
assert api.call_method('VisualizeSheathingLeeway',args=(None,40.,0.)) is False
s={'start':time.monotonic(),'world':None,'last':-1,'rows':[]}
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['callback'])
 if s['world'] and ed.get_game_world()==s['world']:level.editor_request_end_play()
 (out/'visual-test.json').write_text(json.dumps({'reason':reason,'rows':s['rows']},indent=2),encoding='utf-8')
 print('LEEWAY_FINISHED',reason)
def tick(_):
 try:
  if time.monotonic()-s['start']>100:return finish('timeout')
  w=ed.get_game_world()
  if not w:
   if s['world']:finish('ended externally')
   return
  s['world']=w;a=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(a,unreal.ProphecyAgent):return
  n=int(a.get_editor_property('absolute tick debug'))
  if n==s['last']:return
  s['last']=n
  drawn=api.call_method('VisualizeSheathingLeeway',args=(a,40.,0.))
  s['rows'].append({'tick':n,'drawn':drawn})
  if n>=35:
   pos=a.get_pose_reference_mesh().get_socket_location('pelvis')+unreal.Vector(0,0,20)
   forward=a.get_actor_forward_vector();right=a.get_actor_right_vector()
   camloc=pos+forward*170-right*70+unreal.Vector(0,0,25)
   transform=unreal.Transform(location=camloc,rotation=unreal.MathLibrary.find_look_at_rotation(camloc,pos))
   if not s.get('camera'):
    gs=unreal.get_default_object(unreal.GameplayStatics)
    cam=gs.call_method('BeginDeferredActorSpawnFromClass',args=(w,unreal.CameraActor,transform,unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN,None,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
    cam=gs.call_method('FinishSpawningActor',args=(cam,transform,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
    unreal.GameplayStatics.get_player_controller(w,0).set_view_target_with_blend(cam,0)
    s['camera']=cam
   else:s['camera'].set_actor_transform(transform,False,True)
  if n in (70,110):unreal.AutomationLibrary.take_high_res_screenshot(1280,900,str(out/f'leeway-{n}.png'))
  if n==85:
   s['rows'][-1]['hud']=str(unreal.GameplayStatics.get_player_controller(w,0).get_hud())
   unreal.SystemLibrary.execute_console_command(w,f'Shot showui filename="{out / "leeway-hud.png"}" -nosuffix')
  if n>=135:return finish('captured')
 except Exception:return finish(traceback.format_exc())
s['callback']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play();print('LEEWAY_STARTED')
