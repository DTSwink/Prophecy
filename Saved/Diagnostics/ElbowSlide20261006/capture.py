import unreal,json,pathlib,time,traceback,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/ElbowSlide20261006';p.mkdir(exist_ok=True)
mode=sys.argv[1] if len(sys.argv)>1 else 'baseline'
s={'world':None,'last':None,'start':time.monotonic(),'rows':[],'meta':{},'agents':[]}
trace=p.parent/'SlashContacts/live_steps.jsonl';s['offset']=trace.stat().st_size if trace.exists() else 0
cvars=['Prophecy.SlashTraceAgent','Prophecy.SlashTraceFrames'];s['cvars']={c:unreal.SystemLibrary.get_console_variable_int_value(c) for c in cvars}
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
graph=p.parent/'SwordThigh/BlueprintGraph.txt'
if graph.exists():(p/(mode+'-graph.txt')).write_bytes(graph.read_bytes())
bones=['pelvis','spine_01','spine_05','head','upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r','foot_l','foot_r']
root=unreal.ProphecyRootPhysicsLibrary
modifier=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyNNModifierDebugLibrary'))
def v(x):return [x.x,x.y,x.z]
def tr(x):return {'p':v(x.translation),'q':[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w]}
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 for c,val in s['cvars'].items():unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),c+' '+str(val))
 (p/(mode+'.json')).write_text(json.dumps({'reason':reason,'meta':s['meta'],'rows':s['rows']},separators=(',',':')),encoding='utf-8')
 if trace.exists():
  with trace.open('rb') as f:f.seek(s['offset']);(p/(mode+'-nn.jsonl')).write_bytes(f.read())
 if s['world'] is not None and ed.get_game_world()==s['world']:level.editor_request_end_play()
 print('ELBOW_SLIDE_DONE',mode,reason,len(s['rows']))
def tick(_):
 try:
  if time.monotonic()-s['start']>180:finish('timeout');return
  w=ed.get_game_world()
  if not w:
   if s['world'] is not None:finish('World ended')
   return
  if s['world'] is None:s['world']=w
  if w!=s['world']:finish('World replaced');return
  player=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(player,unreal.ProphecyAgent):return
  n=int(player.get_editor_property('tick debug'))
  if n==s['last']:return
  s['last']=n
  if not s['agents']:s['agents']=list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent))
  if n>=900 and not s.get('tracing'):
   for c,val in zip(cvars,[-2,1000]):unreal.SystemLibrary.execute_console_command(w,c+' '+str(val))
   s['tracing']=True
  if not s['meta']:
   s['meta']={'debug':{k:bool(player.get_editor_property(k)) for k in ['bool debug 1','bool debug 2','bool debug 3']},'actors':[a.get_actor_label() for a in s['agents']]}
  if mode=='balance_off' and n>=1150:
   for a in s['agents']:root.set_root_self_balancing(a,False)
  if mode=='wrist_off' and n>=960:unreal.ProphecyAttackWristLibrary.set_left_hand_constraint_global_enabled(player,False)
  if mode=='entry_off' and n>=960:unreal.ProphecyAttackStartInertiaLibrary.set_attack_start_hand_inertia(player,False)
  detailed=900<=n<=1050 or 1120<=n<=1330
  if detailed or n%5==0:
   for a in s['agents']:
    if not a.has_valid_agent_handle():continue
    attack=a.get_nn_attack_state();d=unreal.ProphecyNNDefenseLibrary.get_nn_defense_status(a)
    r={'tick':n,'time':unreal.GameplayStatics.get_time_seconds(w),'actor':a.get_actor_label(),'player':a==player,'mode':str(a.get_simulation_mode()),'state':str(unreal.ProphecyNNDefenseLibrary.get_agent_state(a)),'attack':[str(attack[0]),*attack[1:]] if attack else None,'defense':{'active':d.active,'frame':d.attacker_frame,'steps':d.completed_steps} if d else None,'root':v(a.get_root_low_point()),'actor_p':v(a.get_actor_location()),'velocity':v(a.get_velocity()),'magic':v(root.get_root_magic_velocity(a)),'magic2':v(root.get_root_magic_velocity2(a)),'bones':{}}
    rv=a.get_root_velocity()
    if rv:r['root_velocity']=[v(x) for x in rv]
    window=root.get_continuous_locomotion_root_window(a)
    if window:r['window']=[tr(x) for x in window[0]]
    r['balance']=str(root.get_root_self_balancing_state(a))
    r['cubes']={c.get_name():{'p':v(c.get_world_location()),'v':v(c.get_component_velocity())} for c in a.get_components_by_class(unreal.StaticMeshComponent) if 'magic' in c.get_name().lower()}
    pose=a.read_nn_future_world_pose()
    if pose:
     names,future,presented,alpha=pose;r['alpha']=alpha
     for i,name in enumerate(names):
      b=str(name)
      if b not in bones:continue
      body=a.get_physical_body_state(b);target=a.get_authored_body_world_target(b)
      r['bones'][b]={'future':tr(future[i]),'presented':tr(presented[i]),'body':tr(body[0]) if body else None,'target':tr(target[2]) if target else None,'v':v(body[1]) if body else None,'w':v(body[2]) if body else None}
      if detailed and b in ['head','lowerarm_r','lowerarm_l','hand_r','hand_l']:
       m=a.get_body_magnetization_settings(b);f=a.get_physical_feedback_tolerance(b)
       r['bones'][b]['mag']=[m.linear_strength_scale,m.angular_strength_scale,m.magnetization_enabled] if m else None
       r['bones'][b]['feedback']=[f.linear_tolerance_cm,f.angular_tolerance_degrees] if f else None
       r['bones'][b]['damping']=unreal.ProphecyJointDampingLibrary.get_jolt_joint_angular_damping(a,b)
    if n in [930,970,978,980,982,984,986,990,1000,1120,1150,1160,1200,1250,1300]:r['report']=str(modifier.call_method('PrintNNModifiers',(a,)))
    s['rows'].append(r)
  if n>=(1040 if mode in ['entry_off','length_before','length_after'] else 1330):finish('complete')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play();print('ELBOW_SLIDE_STARTED',mode)
