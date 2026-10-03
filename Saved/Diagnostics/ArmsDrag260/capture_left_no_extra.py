import unreal,pathlib,json,time,traceback,sys
tag=sys.argv[1] if len(sys.argv)>1 else 'baseline'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
folder=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/ArmsDrag260');folder.mkdir(exist_ok=True)
log=pathlib.Path(unreal.Paths.project_log_dir(),'GameAnimationSample3.log');offset=log.stat().st_size
audits=['Prophecy.Recovery.RegionAudit','Prophecy.UpperInertia.Audit','Prophecy.SlashReturn.Audit','Prophecy.ArmCone.Audit']
if tag.startswith('wrap_'):audits.append('Prophecy.ArmCone.TwistAudit')
for c in audits:unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),c+' 1')
s=dict(start=time.monotonic(),last=None,n=0,rows=[])
bones=['pelvis','spine_05','neck_01','upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r']
def tr(t):return dict(p=[t.translation.x,t.translation.y,t.translation.z],q=[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w])
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 w=ed.get_game_world() or ed.get_editor_world()
 for c in audits:unreal.SystemLibrary.execute_console_command(w,c+' 0')
 (folder/(tag+'.json')).write_text(json.dumps(dict(error=error,rows=s['rows']),separators=(',',':')),encoding='utf-8')
 with log.open('rb') as f:f.seek(offset);(folder/(tag+'.log')).write_bytes(f.read())
 if ed.get_game_world():level.editor_request_end_play()
 print('ARMS_DRAG_DONE',error or 'complete',s['n'])
def tick(_):
 try:
  if time.monotonic()-s['start']>80:finish('timeout');return
  w=ed.get_game_world()
  if not w:
   if s['n']:finish('play ended')
   return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t;s['n']+=1
  for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
   if a.is_player_controlled() and int(a.get_editor_property('tick debug'))>=181:
    lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySlashReturnLibrary'))
    lib.call_method('SetBothArmsReturnToNeutralEnabled',(a,False))
   data=a.read_nn_future_world_pose()
   if not data:continue
   names,future,presented,alpha=data
   names=[str(n) for n in names];row=dict(n=s['n'],tick=int(a.get_editor_property('tick debug')),time=t,actor=a.get_name(),player=a.is_player_controlled(),attack=str(a.get_nn_attack_state()),mode=str(a.get_simulation_mode()),future={},presented={})
   for b in bones:
    if b in names:i=names.index(b);row['future'][b]=tr(future[i]);row['presented'][b]=tr(presented[i])
   if a.is_player_controlled():
    sword=a.get_held_sword()
    if sword:
     meshes=sword.get_components_by_class(unreal.StaticMeshComponent)
     blade=next((m for m in meshes if m.get_name()=='sword'),None)
     if blade and blade.static_mesh:
      box=blade.static_mesh.get_bounding_box();grip=a.get_editor_property('sword_grip_transform')
      row['weapon']=dict(actual=tr(blade.get_world_transform()),grip=tr(grip),scale=[grip.scale3d.x,grip.scale3d.y,grip.scale3d.z],lo=[box.min.x,box.min.y,box.min.z],hi=[box.max.x,box.max.y,box.max.z])
   s['rows'].append(row)
   if tag=='temp_legacy' and a.is_player_controlled() and s['n']==1:
    lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyArmConeLibrary'))
    assert lib.call_method('SetTemporaryPreDragFixVersion',(a,True))
   if tag=='no_exit_inertia' and a.is_player_controlled() and s['n']==183:
    lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyUpperBodyInertiaLibrary'))
    lib.call_method('SetAttackUpperBodyInertia',(a,False,.03,0.,.5,1.,unreal.ProphecyUpperHandInertiaSpace.SPINE_LOCAL,1.))
   if tag=='no_post_armed_pose' and a.is_player_controlled() and s['n']>=183:
    lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyArmedPoseLibrary'))
    lib.call_method('StopUpperBodyArmedPose',(a,))
   if tag in ('no_cone_recovery','no_post_cone') and a.is_player_controlled() and s['n']==183:
    lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyArmConeLibrary'))
    lib.call_method('SetArmRepellantCone',(a,False,60.,1000000.,20.,.5,.5,True,5.,60.,10.))
  if s['n']>=400:finish()
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
print('ARMS_DRAG_STARTED')
