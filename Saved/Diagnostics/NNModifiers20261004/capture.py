import unreal,pathlib,json,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/NNModifiers20261004';p.mkdir(exist_ok=True)
mode=sys.argv[1] if len(sys.argv)>1 else 'before'
w=ed.get_game_world()
assert w is None,'Experiments require an owned session'
s=dict(world=w,owned=w is None,last=None,start=time.monotonic(),rows=[],frames=0)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
(p/(mode+'-graph.txt')).write_bytes((p.parent/'SwordThigh/BlueprintGraph.txt').read_bytes())
trace=p.parent/'SlashContacts/live_steps.jsonl';s['trace_start']=trace.stat().st_size if trace.exists() else 0
s['old_trace']=[unreal.SystemLibrary.get_console_variable_int_value(n) for n in ('Prophecy.SlashTraceAgent','Prophecy.SlashTraceFrames')]
for command in ('Prophecy.SlashTraceAgent -2','Prophecy.SlashTraceFrames 1600'):
 unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),command)
def v(x):return [x.x,x.y,x.z]
def tr(x):return dict(p=v(x.translation),q=[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w])
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 for n,value in zip(('Prophecy.SlashTraceAgent','Prophecy.SlashTraceFrames'),s['old_trace']):
  unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),n+' '+str(value))
 (p/(mode+'.json')).write_text(json.dumps(dict(reason=reason,owned=s['owned'],rows=s['rows'])),encoding='utf8')
 if trace.exists():
  with trace.open('rb') as f:f.seek(s['trace_start']);(p/(mode+'-nn.jsonl')).write_bytes(f.read())
 if s['owned'] and s['world'] is not None and ed.get_game_world()==s['world']:level.editor_request_end_play()
 print('HEAD_ENTRY_DONE',mode,reason,len(s['rows']));s['rows'].clear()
def tick(_):
 try:
  if time.monotonic()-s['start']>180:finish('Watchdog');return
  world=ed.get_game_world()
  if world is None:
   if s['world'] is not None:finish('Original Play ended')
   return
  if s['world'] is None:s['world']=world
  if world!=s['world']:finish('World replaced');return
  t=unreal.GameplayStatics.get_time_seconds(world)
  if t==s['last']:return
  s['last']=t;s['frames']+=1
  a=unreal.GameplayStatics.get_player_pawn(world,0)
  if isinstance(a,unreal.ProphecyAgent):
   clock=int(a.get_editor_property('tick debug'))
   if clock==1:unreal.get_default_object(unreal.SystemLibrary).call_method('SetBoolPropertyByName',(a,'bool debug 3',True))
   pose=a.read_nn_future_world_pose()
   if pose:
    names,future,presented,alpha=pose
    bones=('pelvis','spine_01','spine_02','spine_03','spine_04','spine_05','neck_01','neck_02','head','clavicle_l','clavicle_r','upperarm_l','upperarm_r','lowerarm_l','lowerarm_r','hand_l','hand_r','thigh_l','thigh_r','calf_l','calf_r','foot_l','foot_r')
    r=dict(tick=clock,time=t,actor=a.get_name(),attack=list(a.get_nn_attack_state()) if a.get_nn_attack_state() else None,root=v(a.get_root_low_point()),alpha=alpha,bones={})
    r['simulation_mode']=str(a.get_simulation_mode())
    r['drag']=unreal.get_default_object(unreal.ProphecyAttackFootLocomotionLibrary).call_method('GetAttackFootLocomotion',(a,))
    for b in bones:
     i=next(i for i,n in enumerate(names) if str(n)==b)
     body=a.get_physical_body_state(b);target=a.get_authored_body_world_target(b)
     r['bones'][b]=dict(future=tr(future[i]),presented=tr(presented[i]),body=tr(body[0]) if body else None,target=tr(target[2]) if target else None)
     if body:r['bones'][b]['linear_velocity']=v(body[1]);r['bones'][b]['angular_velocity']=v(body[2])
    raw=a.get_locomotion_root_window()
    if raw:r['window']=[v(x.translation) for x in raw[0]]
    r['attack'] = [str(r['attack'][0]), *r['attack'][1:]] if r['attack'] else None
    ghost=unreal.get_default_object(unreal.ProphecyAttackFootLocomotionLibrary).call_method('ReadGhostLocoDrag',(a,))
    if ghost:r['ghost']=[tr(x) for x in ghost[-1]]
    s['rows'].append(r)
   if mode=='observe':
    lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyNNModifierDebugLibrary'))
    first=lib.call_method('PrintNNModifiers',(a,));second=lib.call_method('PrintNNModifiers',(a,))
    assert first==second, 'Observer changed its own accepted state'
    if s['rows']:s['rows'][-1]['report']=str(first)
  if s['frames']>=260:finish('Complete')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
if s['owned']:level.editor_request_begin_play()
print('HEAD_ENTRY_STARTED',mode,'owned',s['owned'])
