import unreal,pathlib,json,time,traceback,math,sys
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/GetUpPhysics20261010'
tag=sys.argv[1] if len(sys.argv)>1 else 'material'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'User Play is active'
s={'world':None,'started':time.monotonic(),'last':None,'rows':[],'released':None}
def mat(mesh):return mesh.get_editor_property('body_instance').get_editor_property('phys_material_override')
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 (out/(tag+'-smoke.json')).write_text(json.dumps({'reason':reason,'rows':s['rows']},indent=2),encoding='utf-8')
 if s['world'] is not None and ed.get_game_world()==s['world']:level.editor_request_end_play()
 print('GETUP_PHYSICS_SMOKE_FINISHED',tag,reason)
def capture(w,a,n,row):
 body=a.get_physical_body_state('hand_r');p=body[0].translation
 unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.ContactExperiment capture getupphysics_'+tag+'_'+str(n)+' at %.9f %.9f %.9f'%(p.x,p.y,p.z))
 s['rows'].append({'tick':n,'inspect':row,'material':str(mat(a.get_pose_reference_mesh()))})
def tick(_):
 try:
  if time.monotonic()-s['started']>150:finish('timeout');return
  w=ed.get_game_world()
  if not w:
   if s['world'] is not None:finish('world ended')
   return
  s['world']=w;a=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(a,unreal.ProphecyAgent):return
  n=int(a.get_editor_property('absolute tick debug'))
  if s['last']==n:return
  s['last']=n;mesh=a.get_pose_reference_mesh()
  if n==9:
   s['saved']=None if tag=='null' else unreal.new_object(unreal.PhysicalMaterial)
   if s['saved']:s['saved'].set_editor_property('friction',.137)
   mesh.set_phys_material_override(s['saved'])
   assert unreal.ProphecyPhysicalProfileLibrary.save_physical_profile_snapshot(a,'1')
   assert unreal.ProphecyGetUpLibrary.set_get_up_lowerbody_tempering(a,True,.25)
   assert unreal.ProphecyGetUpLibrary.set_get_up_upperbody_tempering(a,True,.5)
  if n==29:
   s['other']=unreal.new_object(unreal.PhysicalMaterial);s['other'].set_editor_property('friction',.923)
   mesh.set_phys_material_override(s['other'])
   assert unreal.ProphecyJoltBodyDriveLibrary.set_arms_anti_jiggle(a,False,True)
   assert unreal.ProphecyPhysicalProfileLibrary.set_magnetization_mode(a,.7)
  if n<29:return
  if tag=='null' and n==35:
   assert not unreal.ProphecyGetUpLibrary.get_up(a,4), 'Active get-up rejects duplicate entry'
  if tag=='cancel' and n==35:
   assert a.play_nn_animation_layer(unreal.load_asset('/Game/_mygame/animations/AS_GetUp_Front1'))
  assert a.get_simulation_mode()==unreal.ProphecyAgentSimulationMode.PHYSICAL
  names,future,presented,alpha=a.read_nn_future_world_pose()
  assert all(math.isfinite(x) for v in presented for x in [v.translation.x,v.translation.y,v.translation.z,v.rotation.x,v.rotation.y,v.rotation.z,v.rotation.w])
  for bone in ['pelvis','hand_l','hand_r','foot_l','foot_r']:
   state=a.get_physical_body_state(bone)
   assert state is not None,bone
   p=state[0].translation
   assert all(math.isfinite(x) for x in [p.x,p.y,p.z]),bone
  unreal.SystemLibrary.execute_console_command(w,'Prophecy.GetUp.Inspect')
  data=(out.parent/'GetUp-Inspect.txt').read_bytes();text=data.decode('utf-16' if data.startswith(b'\xff\xfe') else 'utf-8-sig')
  row=next(x for x in text.splitlines() if x.startswith(a.get_name()+' '))
  if n==29:capture(w,a,n,row)
  if n==30:
   assert 'active=1' in row and 'lower_window=1 mode=0.000' in row,row
   assert mat(mesh)==s['saved'],(mat(mesh),s['saved'])
   capture(w,a,n,row)
  if n==31:capture(w,a,n,row)
  if n>30 and 'lower_window=0' in row and s['released'] is None:
   assert ('active=0' if tag=='cancel' else 'active=1') in row and 'mode=1.000' in row,row
   s['released']=n;capture(w,a,n,row)
  if s['released'] is not None and n>=s['released']+2:
   capture(w,a,n,row);finish('passed')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('GETUP_PHYSICS_SMOKE_STARTED',tag)
