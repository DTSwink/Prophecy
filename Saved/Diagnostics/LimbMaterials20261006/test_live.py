import unreal,pathlib,json,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/LimbMaterials20261006'
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyLimbColorLibrary'))
s={'world':None,'phase':0,'start':time.monotonic(),'checks':[],'task':None}
def call(n,*a):return lib.call_method(n,a)
def check(v,label):
 assert v,label
 s['checks'].append(label)
def body(a):return [str(a.get_physical_body_state(x)) for x in ['head','hand_l','hand_r','pelvis','sword']]
def mats(a):return [(c,c.get_material(0)) for c in a.get_components_by_class(unreal.SkinnedMeshComponent) if c.get_name() in ['Mesh','PhysicalMesh'] and c.get_skinned_asset()]
def shot(name):
 s['shot']=p/(name+'.png');s['shot_start']=time.monotonic()
 unreal.SystemLibrary.execute_console_command(s['world'],'HighResShot 1 filename="'+str(s['shot'].resolve())+'"')
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 if ed.get_game_world()==s['world'] and s['world']:
  unreal.GameplayStatics.set_game_paused(s['world'],False);level.editor_request_end_play()
 (p/'test.json').write_text(json.dumps({'reason':reason,'checks':s['checks']},indent=2));print('LIMB_COLOR_TEST',reason)
def tick(_):
 try:
  if time.monotonic()-s['start']>90:finish('timeout');return
  w=ed.get_game_world()
  if not w:return
  if s['world'] is None:s['world']=w
  if w!=s['world']:finish('world replaced');return
  a=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(a,unreal.ProphecyAgent):return
  if s['phase']==0:
   if int(a.get_editor_property('absolute tick debug'))<15:return
   unreal.GameplayStatics.set_game_paused(w,True)
   s['a']=a;s['original']=mats(a);before=body(a)
   others=[x for x in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent) if x!=a]
   other_mats=[mats(x) for x in others]
   names=list(call('GetLimbColorBones'));check(len(names)==23,'23 supported regions')
   check(not call('SetLimbColor',a,'invalid',unreal.LinearColor(1,0,0,1)),'Unknown bone rejected')
   for name in names:check(call('SetLimbColor',a,name,unreal.LinearColor(1,0,0,1)),'Set '+str(name))
   check(all(c.get_material(0)!=m for c,m in s['original']),'Every populated presentation mesh gets color material')
   check([mats(x) for x in others]==other_mats,'Other agents unchanged')
   check(body(a)==before,'Physical body transforms and velocities unchanged by setting colors')
   check(call('ResetLimbColor',a,'None'),'Reset all succeeds')
   check(mats(a)==s['original'],'Reset restores exact original material objects')
   target=a.get_pose_reference_mesh().get_socket_location('pelvis')+unreal.Vector(0,0,10)
   location=target+a.get_actor_forward_vector()*270+a.get_actor_right_vector()*60+unreal.Vector(0,0,30)
   t=unreal.Transform(location=location,rotation=unreal.MathLibrary.find_look_at_rotation(location,target))
   gs=unreal.get_default_object(unreal.GameplayStatics)
   cam=gs.call_method('BeginDeferredActorSpawnFromClass',(w,unreal.CameraActor,t,unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN))
   s['cam']=gs.call_method('FinishSpawningActor',(cam,t))
   unreal.GameplayStatics.get_player_controller(w,0).set_view_target_with_blend(s['cam'],0)
   shot('original');s['phase']=1;return
  if time.monotonic()-s['shot_start']<1 or not s['shot'].exists():return
  if s['phase']==1:
   for bone,col in [('head',(0,1,0,1)),('lowerarm_r',(1,0,0,1)),('hand_l',(0,0.2,1,1)),('foot_r',(1,1,0,1))]:
    check(call('SetLimbColor',a,bone,unreal.LinearColor(*col)),'Visual color '+bone)
   shot('colored');s['phase']=2;return
  if s['phase']==2:
   check(call('ResetLimbColor',a,'head'),'Reset head alone');shot('head_reset');s['phase']=3;return
  if s['phase']==3:
   check(call('ResetLimbColor',a,'None'),'Final reset all')
   check(mats(a)==s['original'],'Final exact material restoration')
   finish('passed')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play();print('LIMB_COLOR_TEST_STARTED')
