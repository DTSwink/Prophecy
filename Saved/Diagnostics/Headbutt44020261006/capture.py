import unreal,json,pathlib,time,traceback,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/Headbutt44020261006'
mode=sys.argv[1] if len(sys.argv)>1 else 'baseline'
switch=int(sys.argv[2]) if len(sys.argv)>2 else 350
end=int(sys.argv[3]) if len(sys.argv)>3 else 590
s={'world':None,'last':None,'start':time.monotonic(),'rows':[],'meta':{},'agents':[]}
trace=p.parent/'SlashContacts/live_steps.jsonl';s['offset']=trace.stat().st_size if trace.exists() else 0
cvars=['Prophecy.SlashTraceAgent','Prophecy.SlashTraceFrames'];s['cvars']={c:unreal.SystemLibrary.get_console_variable_int_value(c) for c in cvars}
modifier=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyNNModifierDebugLibrary'))
bones=['pelvis','spine_01','spine_03','spine_05','neck_01','neck_02','head','hand_l','hand_r','foot_l','foot_r']
def v(x):return [x.x,x.y,x.z]
def tr(x):return {'p':v(x.translation),'q':[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w]}
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 for c,val in s['cvars'].items():unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),c+' '+str(val))
 (p/(mode+'.json')).write_text(json.dumps({'reason':reason,'mode':mode,'switch':switch,'meta':s['meta'],'rows':s['rows']},separators=(',',':')),encoding='utf8')
 if trace.exists():
  with trace.open('rb') as f:f.seek(s['offset']);(p/(mode+'-nn.jsonl')).write_bytes(f.read())
 if s['world'] is not None and ed.get_game_world()==s['world']:level.editor_request_end_play()
 print('HEADBUTT_DONE',mode,reason,len(s['rows']))
def tick(_):
 try:
  if time.monotonic()-s['start']>150:finish('timeout');return
  w=ed.get_game_world()
  if not w:
   if s['world'] is not None:finish('world ended')
   return
  if s['world'] is None:s['world']=w
  if w!=s['world']:finish('world replaced');return
  player=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(player,unreal.ProphecyAgent):return
  n=int(player.get_editor_property('absolute tick debug'))
  if n==s['last']:return
  s['last']=n
  if not s['agents']:s['agents']=list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent))
  if not s['meta']:s['meta']={'debug':{k:bool(player.get_editor_property(k)) for k in ['bool debug 1','bool debug 2','bool debug 3']},'actors':[a.get_actor_label() for a in s['agents']]}
  if n>=300 and not s.get('tracing'):
   for c,val in zip(cvars,[-2,1200]):unreal.SystemLibrary.execute_console_command(w,c+' '+str(val))
   s['tracing']=True
  if n>=switch:
   if mode.startswith('blend_'):
    blend=float(mode.split('_',1)[1])
    assert unreal.ProphecyAttackStartInertiaLibrary.set_attack_start_hand_inertia(player,True,0.,blend,1.,1.,1.,1.,True,True)
   if mode=='motion_off':assert unreal.ProphecyAttackMotionInertiaLibrary.set_attack_motion_inertia(player,False)
   if mode=='feedback_off':assert unreal.ProphecyAttackNNFeedbackLibrary.set_attack_nn_feedback(player,False,False,False,False,False)
   if mode=='core_feedback_off':assert unreal.ProphecyAttackNNFeedbackLibrary.set_attack_nn_feedback(player,False,True,True,True,False)
   if mode=='hand_feedback_off':assert unreal.ProphecyAttackNNFeedbackLibrary.set_attack_nn_feedback(player,True,False,True,True,False)
  for a in s['agents']:
   if not a.has_valid_agent_handle():continue
   attack=a.get_nn_attack_state()
   r={'tick':n,'local_tick':int(a.get_editor_property('tick debug')),'absolute_tick':int(a.get_editor_property('absolute tick debug')),'time':unreal.GameplayStatics.get_time_seconds(w),'actor':a.get_actor_label(),'player':a==player,'mode':str(a.get_simulation_mode()),'attack':[str(attack[0]),*attack[1:]] if attack else None,'root':v(a.get_root_low_point()),'bones':{}}
   pose=a.read_nn_future_world_pose()
   if pose:
    names,future,presented,alpha=pose;r['alpha']=alpha
    for i,name in enumerate(names):
     b=str(name)
     if b not in bones:continue
     body=a.get_physical_body_state(b);target=a.get_authored_body_world_target(b)
     r['bones'][b]={'future':tr(future[i]),'presented':tr(presented[i]),'body':tr(body[0]) if body else None,'target':tr(target[2]) if target else None}
   if 360<=n<=520 and n%10==0:r['report']=str(modifier.call_method('PrintNNModifiers',(a,)))
   s['rows'].append(r)
  if n%60==0:(p/(mode+'-progress.json')).write_text(json.dumps({'tick':n,'rows':len(s['rows'])}))
  if n>=end:finish('complete')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play();print('HEADBUTT_STARTED',mode)
