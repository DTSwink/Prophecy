"""Owned visual/timing check, using the user's current PressureBomb material.
No asset writes; pauses only its own Play briefly for the two screenshots.
"""
import unreal,pathlib,time,json,traceback
out=pathlib.Path(unreal.Paths.project_dir())/'Saved/Diagnostics/BombFragmentFade'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
state={'world':None,'start':time.monotonic(),'last':-1,'rows':[],'shots':set(),'task':None}
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyBombLibrary'))

def spawn(w,cls,pos,rot=unreal.Rotator()):
 tr=unreal.Transform(location=pos,rotation=rot);gs=unreal.get_default_object(unreal.GameplayStatics)
 a=gs.call_method('BeginDeferredActorSpawnFromClass',(w,cls,tr,unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN,None,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
 return gs.call_method('FinishSpawningActor',(a,tr,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))

def finish(reason):
 unreal.unregister_slate_post_tick_callback(state['cb'])
 if state['world'] and ed.get_game_world()==state['world']:
  unreal.GameplayStatics.set_game_paused(state['world'],False);level.editor_request_end_play()
 (out/'visual.json').write_text(json.dumps({'reason':reason,'rows':state['rows'],'shots':sorted(state['shots'])},indent=2))
 print('FRAGMENT_FADE_VERIFY',reason)

def tick(_):
 try:
  if time.monotonic()-state['start']>180:return finish('timeout')
  w=ed.get_game_world()
  if not w:
   if state['world']:return finish('Play ended externally')
   return
  if state['world'] is None:state['world']=w
  if w!=state['world']:return finish('Play replaced')
  if state['task']:
   if state['task'].is_task_done():state['task']=None;unreal.GameplayStatics.set_game_paused(w,False)
   return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==state['last']:return
  state['last']=t
  if not state.get('pieces'):
   centre=unreal.Vector(2000,0,200)
   a=spawn(w,unreal.StaticMeshActor,centre);m=a.static_mesh_component
   m.set_mobility(unreal.ComponentMobility.MOVABLE)
   m.set_static_mesh(unreal.load_asset('/Game/Fab/CC0_-_Bomb/cc0_bomb/StaticMeshes/cc0_bomb'))
   source=unreal.load_asset('/Game/Fab/CC0_-_Bomb/cc0_bomb/Materials/PressureBomb');m.set_material(0,source)
   args=(m,0.,0.,1.,1.,2.,0.,unreal.ProphecyVDBEffect.SHOCKWAVE_EXPLOSION,.001,30.,0.,0.,0.,unreal.Rotator(),4.,None,unreal.Rotator(),True,True,2.)
   assert api.call_method('LightBombFuse',args)
   pieces=[x for x in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.StaticMeshActor) if x.static_mesh_component.static_mesh and x.static_mesh_component.static_mesh.get_name().startswith('SM_BombFragment_') and (x.get_actor_location()-centre).length()<100]
   assert len(pieces)==20,len(pieces)
   for x in pieces:
    p=x.static_mesh_component
    assert p.get_material(0)==source,'Original material retained before fade'
    c=p.get_center_of_mass();d=c-(centre+unreal.Vector(-1.0239047,0,-1.2153458));d=d/d.length()
    p.set_simulate_physics(False);x.set_actor_location(centre+d*16,False,True)
   state['pieces']=pieces;state['n']=0;state['source']=source
   camera_pos=centre+unreal.Vector(88,-100,42)
   state['camera']=spawn(w,unreal.CameraActor,camera_pos,unreal.MathLibrary.find_look_at_rotation(camera_pos,centre))
   state['camera'].get_component_by_class(unreal.CameraComponent).set_field_of_view(45)
   pc=unreal.GameplayStatics.get_player_controller(w,0)
   if pc:pc.set_view_target_with_blend(state['camera'])
   return
  state['n']+=1;n=state['n']
  alive=[p for p in state['pieces'] if unreal.SystemLibrary.is_valid(p)]
  if not alive:
   assert {'solid','half'}.issubset(state['shots']),state['shots']
   return finish('passed')
  mat=alive[0].static_mesh_component.get_material(0)
  alpha=mat.get_scalar_parameter_value('FragmentOpacity') if isinstance(mat,unreal.MaterialInstanceDynamic) else 1.
  state['rows'].append({'n':n,'alive':len(alive),'opacity':alpha,'material':mat.get_path_name()})
  assert 0<=alpha<=1 and len(alive)==20
  if isinstance(mat,unreal.MaterialInstanceDynamic):
   assert all(p.static_mesh_component.get_material(0)==mat for p in alive)
   assert mat.get_blend_mode()==unreal.BlendMode.BLEND_TRANSLUCENT
  shot='solid' if n==30 else ('half' if .49<=alpha<=.51 else None)
  if shot and shot not in state['shots']:
   state['shots'].add(shot);unreal.GameplayStatics.set_game_paused(w,True)
   state['task']=unreal.AutomationLibrary.take_high_res_screenshot(1000,700,str(out/(shot+'.png')),camera=state['camera'])
 except Exception:return finish(traceback.format_exc())

state['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
print('FRAGMENT_FADE_VERIFY_STARTED')
