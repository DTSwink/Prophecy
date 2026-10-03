import unreal,pathlib,json,time,traceback,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/PikeSword20261003';p.mkdir(exist_ok=True)
mode=sys.argv[1] if len(sys.argv)>1 else 'baseline'
condition=mode.removesuffix('_fourth')
target_ordinal=4 if mode.endswith('_fourth') else 2
count=int(sys.argv[2]) if len(sys.argv)>2 else (930 if mode=='baseline' else 550)
w=ed.get_game_world();assert w is None,'Controlled comparisons require an owned Play session'
s=dict(world=None,last=None,start=time.monotonic(),rows=[],frames=0,attack_count=0,was_attack=False,changes=[],metadata={})
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
(p/(mode+'-graph.txt')).write_bytes((p.parent/'SwordThigh/BlueprintGraph.txt').read_bytes())
trace=p.parent/'SlashContacts/live_steps.jsonl';s['offset']=trace.stat().st_size if trace.exists() else 0
s['cvars']={n:unreal.SystemLibrary.get_console_variable_int_value(n) for n in ('Prophecy.SlashTraceAgent','Prophecy.SlashTraceFrames')}
for command in ('Prophecy.SlashTraceAgent -2','Prophecy.SlashTraceFrames 1000'):unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),command)
def v(x):return [x.x,x.y,x.z]
def tr(x):return dict(p=v(x.translation),q=[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w],s=v(x.scale3d))
def call(cls,fn,args):return unreal.get_default_object(cls).call_method(fn,args)
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 for n,value in s['cvars'].items():unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),n+' '+str(value))
 (p/(mode+'.json')).write_text(json.dumps(dict(reason=reason,owned=True,rows=s['rows'],changes=s['changes'],metadata=s['metadata'])),encoding='utf8')
 if trace.exists():
  with trace.open('rb') as f:f.seek(s['offset']);(p/(mode+'-nn.jsonl')).write_bytes(f.read())
 if s['world'] is not None and ed.get_game_world()==s['world']:level.editor_request_end_play()
 print('PIKE_CAPTURE_DONE',mode,reason,len(s['rows']));s['rows'].clear()
def tick(_):
 try:
  if time.monotonic()-s['start']>150:finish('Watchdog');return
  world=ed.get_game_world()
  if world is None:
   if s['world'] is not None:finish('Owned Play ended')
   return
  if s['world'] is None:s['world']=world
  if world!=s['world']:finish('World replaced');return
  t=unreal.GameplayStatics.get_time_seconds(world)
  if t==s['last']:return
  s['last']=t;s['frames']+=1
  a=unreal.GameplayStatics.get_player_pawn(world,0)
  if isinstance(a,unreal.ProphecyAgent):
   clock=int(a.get_editor_property('tick debug'));attack=a.get_nn_attack_state()
   active=attack is not None
   if active and not s['was_attack']:s['attack_count']+=1
   s['was_attack']=active
   pose=a.read_nn_future_world_pose()
   if pose:
    names,future,presented,alpha=pose
    r=dict(tick=clock,time=t,attack=[str(attack[0]),*attack[1:]] if active else None,attack_count=s['attack_count'],alpha=alpha,bones={},root=v(a.get_root_low_point()),actor=tr(a.get_actor_transform()),mode=str(a.get_simulation_mode()),drag=call(unreal.ProphecyAttackFootLocomotionLibrary,'GetAttackFootLocomotion',(a,)))
    for i,b in enumerate(names):
     b=str(b);body=a.get_physical_body_state(b)
     r['bones'][b]=dict(future=tr(future[i]),presented=tr(presented[i]),body=tr(body[0]) if body else None)
    sw=a.get_held_sword()
    if sw:
     r['sword']=tr(sw.get_actor_transform())
     r['sword_components']={c.get_name():tr(c.get_world_transform()) for c in sw.get_components_by_class(unreal.SceneComponent)}
     if not s['metadata']:
      s['metadata']=dict(sword_class=sw.get_class().get_name(),sword_grip=tr(a.get_editor_property('SwordGripTransform')),sword_socket=str(a.get_editor_property('SwordHandSocket')),
       components=[dict(name=c.get_name(),class_name=c.get_class().get_name()) for c in sw.get_components_by_class(unreal.SceneComponent)])
    s['rows'].append(r)
   if s['attack_count']==target_ordinal and active:
    if mode in ('hands_off','entry_off','hands_drag_off','clean_attack'):call(unreal.ProphecyAttackStartInertiaLibrary,'SetAttackStartHandInertia',(a,False,0.,.2,1.,1.,1.,1.,True,True))
    if mode in ('entry_off','clean_attack'):
     call(unreal.ProphecyAttackStartInertiaLibrary,'SetAttackStartPelvisInertia',(a,False,19,1.,10,1.))
     call(unreal.ProphecyAttackStartInertiaLibrary,'SetAttackStartFKCoreInertia',(a,False,0.,.1,.25,1.,1.))
    if mode in ('hands_drag_off','clean_attack'):call(unreal.ProphecyAttackFootLocomotionLibrary,'SetAttackFootLocomotion',(a,False,unreal.ProphecyAttackFootLocomotionMode.RUN,40.,15.,.05,0.,0.,0.,1.))
    if condition=='drag_off':call(unreal.ProphecyAttackFootLocomotionLibrary,'SetAttackFootLocomotion',(a,False,unreal.ProphecyAttackFootLocomotionMode.RUN,40.,15.,.05,0.,0.,0.,1.))
    if mode=='pelvis_off':call(unreal.ProphecyAttackStartInertiaLibrary,'SetAttackStartPelvisInertia',(a,False,19,1.,10,1.))
    if mode=='core_off':call(unreal.ProphecyAttackStartInertiaLibrary,'SetAttackStartFKCoreInertia',(a,False,0.,.1,.25,1.,1.))
    if mode=='foot_inertia_off':call(unreal.ProphecyAttackStartInertiaLibrary,'SetAttackStartFootInertia',(a,False,5,1.,5,1.))
    if mode=='kinematic' and a.get_simulation_mode()!=unreal.ProphecyAgentSimulationMode.KINEMATIC:a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
    if mode!='baseline' and not s['changes']:s['changes'].append(dict(tick=clock,mode=mode))
  if s['frames']>=count:finish('Complete')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play();print('PIKE_CAPTURE_STARTED',mode,count)
