import unreal,json,pathlib,time,traceback,sys
mode=sys.argv[1] if len(sys.argv)>1 else 'baseline'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyRootPhysicsLibrary'))
s={'start':time.monotonic(),'rows':[],'owned':not bool(ed.get_game_world()),'seen':False}
out=pathlib.Path(unreal.Paths.project_saved_dir())/('Diagnostics/LegFeedbackIsolation/collision_launch_'+mode+'.json')
def v(x):return [x.x,x.y,x.z]
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 if s['owned'] and ed.get_game_world():level.editor_request_end_play()
 out.write_text(json.dumps({'error':error,'rows':s['rows']},indent=1))
 print('COLLISION_LAUNCH_TRACE',error or 'complete',len(s['rows']))
def tick(_):
 try:
  if time.monotonic()-s['start']>70:return finish('wall timeout')
  w=ed.get_game_world()
  if not w:
   if s['seen']:finish()
   return
  s['seen']=True
  t=unreal.GameplayStatics.get_time_seconds(w)
  for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
   if not a.has_valid_agent_handle():continue
   mesh=a.get_pose_reference_mesh()
   r={'t':t,'actor':a.get_name(),'root':v(a.get_root_low_point()),'pelvis':v(mesh.get_socket_location('pelvis')),
      'magic1':v(api.call_method('GetRootMagicVelocity',(a,))), 'magic2':v(api.call_method('GetRootMagicVelocity2',(a,))),
      'angular2':v(api.call_method('GetRootMagicAngVelocity2',(a,))),'tolerances':{}}
   pose=a.read_nn_future_world_pose()
   if pose:
    names,future,presented,alpha=pose
    pi=list(map(str,names)).index('pelvis')
    r['target_pelvis']=v(presented[pi].translation)
    r['future_pelvis']=v(future[pi].translation)
   body=a.get_physical_body_state('pelvis')
   if body:r['pelvis_velocity']=v(body[1])
   for b in ('pelvis','thigh_l','foot_l','ball_l','thigh_r','foot_r','ball_r','hand_r','upperarm_r','spine_01'):
    f=a.get_physical_feedback_tolerance(b)
    r['tolerances'][b]=[f.linear_tolerance_cm,f.angular_tolerance_degrees] if f else None
   s['rows'].append(r)
   if mode=='zero_spin':api.call_method('SetRootMagicAngVelocity2',(a,unreal.Vector(),False))
   if mode=='no_feedback':a.set_all_physical_feedback_tolerances(100000000.0,1000.0)
  if t>10:finish()
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
if s['owned']:level.editor_request_begin_play()
print('COLLISION_LAUNCH_TRACE armed')
