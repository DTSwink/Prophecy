import unreal,json,pathlib,time,traceback,math
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(), 'Do not interrupt user PIE'
s={'rows':[],'start':time.monotonic(),'refs':{}}
def length(v):return math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['handle']);level.editor_request_end_play()
 p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/DodgeMismatch/parry_wrist_clamp.json'
 p.write_text(json.dumps({'error':error,'rows':s['rows']},separators=(',',':')));print('WRIST_CLAMP_CAPTURE',len(s['rows']),error)
def tick(dt):
 try:
  w=ed.get_game_world()
  if not w:return
  if time.monotonic()-s['start']>100:raise RuntimeError('timeout')
  t=unreal.GameplayStatics.get_time_seconds(w)
  for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
   if not a.has_valid_agent_handle():continue
   name=a.get_name();mesh=a.get_pose_reference_mesh()
   if name not in s['refs']:
    ref=unreal.AnimPoseExtensions.get_reference_pose(mesh.get_skeletal_mesh_asset().skeleton)
    s['refs'][name]=[unreal.AnimPoseExtensions.get_bone_pose(ref,'hand_'+side).translation for side in ['l','r']]
   phase='original' if t<4 else 'hand_clamp'
   for i,side in enumerate(['l','r']):
    f=mesh.get_socket_transform('lowerarm_'+side);h=mesh.get_socket_transform('hand_'+side)
    local=unreal.MathLibrary.inverse_transform_location(f,h.translation);offset=s['refs'][name][i]
    status=unreal.ProphecyNNDefenseLibrary.get_nn_defense_status(a)
    s['rows'].append({'t':t,'name':name,'phase':phase,'side':side,'state':str(unreal.ProphecyNNDefenseLibrary.get_agent_state(a)),'mode':str(a.get_simulation_mode()),'gap':length(local-offset),'length':length(local),'ref_length':length(offset),'steps':status.completed_steps if status else 0})
   if t>=4:
    unreal.ProphecyNNDefenseLibrary.set_parry_forearm_clamp(a,False,0)
    unreal.ProphecyNNDefenseLibrary.set_parry_hand_clamp(a,True,0)
  if t>=8:finish()
 except Exception:finish(traceback.format_exc())
s['handle']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
