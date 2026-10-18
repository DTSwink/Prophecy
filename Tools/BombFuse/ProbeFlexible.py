"""Owned Play verification. Does not edit or save the user's scene or Blueprint."""
import unreal,pathlib,time,json,math,traceback
root=pathlib.Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');out=root/'Saved/Diagnostics/BombFuseFlexible'
rig=json.loads((out/'rig.json').read_text());arc=rig['arc'];centers=rig['centers'];length=arc[-1]
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
s={'world':None,'start':time.monotonic(),'n':0,'last':-1,'rows':[],'task':None}
names=['strap_root']+[f'strap_{i:02d}' for i in range(1,6)]+['strap_tip']
sk=unreal.load_asset('/Game/_mygame/BombGenerated/SK_BombFuse');modifier=unreal.SkeletonModifier();assert modifier.set_skeletal_mesh(sk)
refs=[modifier.get_bone_transform(name,True) for name in names]
def vec(p):return [p.x,p.y,p.z]
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['callback'])
 if s['world'] and ed.get_game_world()==s['world']:
  unreal.GameplayStatics.set_game_paused(s['world'],False);level.editor_request_end_play()
 (out/'probe.json').write_text(json.dumps({'reason':reason,'rows':s['rows']},separators=(',',':')))
 print('FLEXIBLE_FUSE_PROBE',reason)
def spawn(w,cls,pos,rot=unreal.Rotator()):
 tr=unreal.Transform(location=pos,rotation=rot);lib=unreal.get_default_object(unreal.GameplayStatics)
 a=lib.call_method('BeginDeferredActorSpawnFromClass',(w,cls,tr,unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN,None,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
 return lib.call_method('FinishSpawningActor',(a,tr,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
def expected_tip(visual,remaining):
 distance=max(0.,min(1.,(remaining-.01)/.99))*length
 i=0
 while i+2<len(arc) and arc[i+1]<distance:i+=1
 def skin(k):
  u=arc[k]/length*5;j=min(4,int(u));t=u-j;p=unreal.Vector(*centers[k])
  a=visual.get_socket_transform(names[j]).transform_location(refs[j].inverse_transform_location(p))
  b=visual.get_socket_transform(names[j+1]).transform_location(refs[j+1].inverse_transform_location(p))
  return a*(1-t)+b*t
 a,b=skin(i),skin(i+1);t=(distance-arc[i])/(arc[i+1]-arc[i]);d=b-a
 return a*(1-t)+b*t,d/d.length()
def tick(_):
 try:
  if time.monotonic()-s['start']>180:return finish('timeout')
  w=ed.get_game_world()
  if not w:
   if s['world']:return finish('ended externally')
   return
  if s['world'] is None:
   s['world']=w;s['bombs']=[];s['visuals']=[];s['meshes']=[]
   for y,stiffness in [(0,0),(20,1000)]:
    a=spawn(w,unreal.StaticMeshActor,unreal.Vector(2000,y,150));m=a.static_mesh_component
    m.set_mobility(unreal.ComponentMobility.MOVABLE);m.set_static_mesh(unreal.load_asset('/Game/Fab/CC0_-_Bomb/cc0_bomb/StaticMeshes/cc0_bomb'))
    m.set_material(0,unreal.load_asset('/Game/Fab/CC0_-_Bomb/cc0_bomb/Materials/PressureBomb'))
    assert unreal.ProphecyBombLibrary.set_bomb_fuse_stiffness(m,stiffness)
    visual=a.get_component_by_class(unreal.ProphecyHolsterStrapComponent);visual.max_simulation_distance=0
    assert visual and visual.get_num_bones()==7
    s['bombs'].append(a);s['meshes'].append(m);s['visuals'].append(visual)
   pos=unreal.Vector(2010,-36,159);rot=unreal.MathLibrary.find_look_at_rotation(pos,unreal.Vector(2000,0,151))
   s['camera']=spawn(w,unreal.CameraActor,pos,rot);s['camera'].get_component_by_class(unreal.CameraComponent).set_field_of_view(40)
   pc=unreal.GameplayStatics.get_player_controller(w,0)
   if pc:pc.set_view_target_with_blend(s['camera'])
   return
  if w!=s['world']:return finish('Play changed')
  if s['task']:
   if s['task'].is_task_done():s['task']=None;unreal.GameplayStatics.set_game_paused(w,False)
   return
  frame=unreal.GameplayStatics.get_time_seconds(w)
  if frame==s['last']:return
  s['last']=frame;n=s['n'];s['n']+=1
  row={'n':n,'poses':[]}
  for a,v in zip(s['bombs'],s['visuals']):
   if not unreal.SystemLibrary.is_valid(a):continue
   cs={name:vec(v.get_socket_transform(name,unreal.RelativeTransformSpace.RTS_COMPONENT).translation) for name in names}
   assert all(math.isfinite(x) for p in cs.values() for x in p)
   assert max(abs(x) for x in cs['strap_root'])<.001
   assert v.get_collision_enabled()==unreal.CollisionEnabled.NO_COLLISION
   row['poses'].append(cs)
  if n==120:
   emitter=unreal.load_asset('/Niagara/DefaultAssets/Templates/Systems/FountainLightweight');assert emitter
   assert unreal.ProphecyBombLibrary.light_bomb_fuse(s['meshes'][0],1.,200.,1000.,500.,2.,0.,unreal.ProphecyVDBEffect.SHOCKWAVE_EXPLOSION,.03,30.,.5,0.,.5,unreal.Rotator(),1.,emitter)
   sparks=[c for c in unreal.ObjectIterator(unreal.NiagaraComponent) if c.get_world()==w and c.get_asset()==emitter]
   assert len(sparks)==1,len(sparks);s['sparks']=sparks[0]
  if 121<=n<300:
   v=s['visuals'][0];remaining=v.get_material(1).get_scalar_parameter_value('FuseRemaining');p,d=expected_tip(v,remaining)
   sparks=s['sparks'];row['tip_error']=(sparks.get_world_location()-p).length();row['direction_dot']=unreal.MathLibrary.dot_vector_vector(sparks.get_forward_vector(),d)
   row['remaining']=remaining
   assert row['tip_error']<.02,row
   assert row['direction_dot']>.999,row
  s['rows'].append(row)
  if n==240:
   unreal.GameplayStatics.set_game_paused(w,True)
   s['task']=unreal.AutomationLibrary.take_high_res_screenshot(1000,700,str(out/'flexible-burning.png'),camera=s['camera']);return
  if n==300:
   assert unreal.ProphecyBombLibrary.hide_bomb_fuse(s['meshes'][0])
   assert not s['visuals'][0].is_component_tick_enabled()
   assert not unreal.ProphecyBombLibrary.set_bomb_fuse_stiffness(s['meshes'][0],20)
  if 300<=n<=320:
   assert s['visuals'][0].get_material(1).get_scalar_parameter_value('FuseRemaining')==-1
   assert not unreal.SystemLibrary.is_valid(s['sparks'])
  if n==320:
   unreal.GameplayStatics.set_game_paused(w,True)
   s['task']=unreal.AutomationLibrary.take_high_res_screenshot(1000,700,str(out/'hidden-fuse.png'),camera=s['camera']);return
  if n==322:
   assert unreal.ProphecyBombLibrary.light_bomb_fuse(s['meshes'][0],0.,200.,1000.,500.,2.,0.,unreal.ProphecyVDBEffect.SHOCKWAVE_EXPLOSION,.03,30.,.5,0.,.5,unreal.Rotator(),1.,None,unreal.Rotator(),True)
   assert not unreal.SystemLibrary.is_valid(s['bombs'][0])
   return finish('complete')
  for i,a in enumerate(s['bombs']):
   if not unreal.SystemLibrary.is_valid(a):continue
   a.set_actor_location_and_rotation(unreal.Vector(2000+1.5*math.sin(n*.09),20*i,150+.7*math.sin(n*.07)),unreal.Rotator(pitch=12*math.sin(n*.06),yaw=10*math.sin(n*.04)),False,False)
 except Exception:return finish(traceback.format_exc())
s['callback']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play();print('Flexible fuse owned Play probe queued;180s watchdog.')
