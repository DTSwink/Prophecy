import unreal,pathlib,json,time,traceback,sys,shutil,hashlib
tag=sys.argv[1] if len(sys.argv)>1 else 'baseline'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
folder=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/RunHandThigh');folder.mkdir(exist_ok=True)
trace=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/SlashContacts/nn_inputs.jsonl')
offset=trace.stat().st_size if trace.exists() else 0
owned=not bool(ed.get_game_world())
model_backup={}
log=pathlib.Path(unreal.Paths.project_log_dir(),'GameAnimationSample3.log');log_offset=log.stat().st_size
assert owned,'Preserve user Play'
audits=['Prophecy.UpperInertia.Audit','Prophecy.SlashReturn.Audit','Prophecy.ArmCone.Audit','Prophecy.ArmCone.TwistAudit']
for c in audits:unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),c+' 1')
if tag in ('feedback','sheathed','zero_gaze'):
 assert owned,'Model probe requires an owned session'
 live=pathlib.Path(unreal.Paths.project_content_dir(),'locomotion/NN')
 for name in ['prophecy_upper_body_b100.onnx','prophecy_upper_body_runtime.json']:
  model_backup[name]=(live/name).read_bytes()
  (folder/('original_'+name)).write_bytes(model_backup[name])
 for name in model_backup:shutil.copy2(folder/(tag+'_probe')/name,live/name)
w=ed.get_game_world() or ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Prophecy.NNInputTraceFrames 240')
s=dict(start=time.monotonic(),last=None,n=0,rows=[])
bones=['pelvis','spine_05','neck_01','clavicle_l','clavicle_r','upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r','thigh_l','calf_l','foot_l','thigh_r','calf_r','foot_r']
def tr(t):return dict(p=[t.translation.x,t.translation.y,t.translation.z],q=[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w])
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 unreal.SystemLibrary.execute_console_command(ed.get_game_world() or ed.get_editor_world(),'Prophecy.NNInputTraceFrames 0')
 (folder/(tag+'.json')).write_text(json.dumps(dict(error=error,owned=owned,rows=s['rows']),separators=(',',':')))
 for c in audits:unreal.SystemLibrary.execute_console_command(ed.get_game_world() or ed.get_editor_world(),c+' 0')
 with log.open('rb') as f:f.seek(log_offset);(folder/(tag+'.log')).write_bytes(f.read())
 if trace.exists():
  with trace.open('rb') as f:f.seek(offset);(folder/(tag+'_nn.jsonl')).write_bytes(f.read())
 for name,contents in model_backup.items():
  (live/name).write_bytes(contents)
  assert (live/name).read_bytes()==contents
 if owned and ed.get_game_world():level.editor_request_end_play()
 print('RUN_THIGH_DONE',tag,error or 'complete',s['n'])
def tick(_):
 try:
  if time.monotonic()-s['start']>90:finish('timeout');return
  w=ed.get_game_world()
  if not w:
   if s['n']:finish('play ended')
   return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t;s['n']+=1
  for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
   if not a.is_player_controlled():continue
   data=a.read_nn_future_world_pose()
   if not data:continue
   names,future,presented,alpha=data;names=[str(n) for n in names]
   row=dict(tick=int(a.get_editor_property('tick debug')),time=t,actor=a.get_name(),attack=str(a.get_nn_attack_state()),mode=str(a.get_simulation_mode()),sword=bool(a.get_held_sword()),future={},presented={},mesh={})
   mesh=next((m for m in a.get_components_by_class(unreal.SkeletalMeshComponent) if m.get_name()=='PhysicalMesh'),None)
   row['meshes']={m.get_name():{'visible':m.is_visible(),'bones':{b:tr(m.get_socket_transform(b,unreal.RelativeTransformSpace.RTS_WORLD)) for b in bones+['index_03_l','middle_03_l','ring_03_l','pinky_03_l'] if m.get_bone_index(b)>=0}} for m in a.get_components_by_class(unreal.SkinnedMeshComponent)}
   for b in bones:
    if b in names:
     i=names.index(b);row['future'][b]=tr(future[i]);row['presented'][b]=tr(presented[i])
     if mesh:row['mesh'][b]=tr(mesh.get_socket_transform(b,unreal.RelativeTransformSpace.RTS_WORLD))
   sword=a.get_held_sword()
   if sword:
    blade=next((m for m in sword.get_components_by_class(unreal.StaticMeshComponent) if m.get_name()=='sword'),None)
    if blade and blade.static_mesh:
     box=blade.static_mesh.get_bounding_box();grip=a.get_editor_property('sword_grip_transform')
     row['weapon']=dict(actual=tr(blade.get_world_transform()),grip=tr(grip),lo=[box.min.x,box.min.y,box.min.z],hi=[box.max.x,box.max.y,box.max.z])
   s['rows'].append(row)
   if tag=='wrist_roll205_off' and row['tick']>=186:
    lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyArmConeLibrary'))
    lib.call_method('SetArmRepellantCone',(a,True,60.,150.,20.,1.5,.5,False,15.,75.,20.,500.))
  if s['n']>=320:finish()
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
if owned:level.editor_request_begin_play()
print('RUN_THIGH_STARTED',tag,'owned',owned)


