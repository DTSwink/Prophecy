import unreal,pathlib,json,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/HeadSwingAudit20261003';p.mkdir(exist_ok=True)
import sys
mode=sys.argv[1] if len(sys.argv)>1 else 'baseline'
w=ed.get_game_world()
assert mode=='baseline' or w is None,'Variants require an owned session'
s=dict(world=w,owned=w is None,last=None,start=time.monotonic(),rows=[],frames=0)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
(p/(mode+'-graph.txt')).write_bytes((p.parent/'SwordThigh/BlueprintGraph.txt').read_bytes())
trace=p.parent/'SlashContacts/live_steps.jsonl';s['trace_start']=trace.stat().st_size if trace.exists() else 0
trace2=p.parent/'SlashContacts/nn_inputs.jsonl';s['trace2_start']=trace2.stat().st_size if trace2.exists() else 0
s['old_nntrace']=unreal.SystemLibrary.get_console_variable_int_value('Prophecy.NNInputTraceFrames')
s['old_trace']=[unreal.SystemLibrary.get_console_variable_int_value(n) for n in ('Prophecy.SlashTraceAgent','Prophecy.SlashTraceFrames')]
for command in ('Prophecy.SlashTraceAgent -2','Prophecy.SlashTraceFrames 420'):
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
 unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.NNInputTraceFrames '+str(s['old_nntrace']))
 if trace2.exists():
  with trace2.open('rb') as f:f.seek(s['trace2_start']);(p/(mode+'-inputs.jsonl')).write_bytes(f.read())
 print('HEAD_ENTRY_DONE',mode,reason,len(s['rows']));s['rows'].clear()
def tick(_):
 try:
  if time.monotonic()-s['start']>90:finish('Watchdog');return
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
   pose=a.read_nn_future_world_pose()
   if pose:
    names,future,presented,alpha=pose
    bones=('pelvis','spine_01','spine_02','spine_03','spine_04','spine_05','neck_01','neck_02','head','clavicle_l','clavicle_r','hand_l','hand_r','thigh_l','thigh_r','calf_l','calf_r','foot_l','foot_r')
    r=dict(tick=clock,time=t,actor=a.get_name(),attack=str(a.get_nn_attack_state()),root=v(a.get_root_low_point()),alpha=alpha,bones={})
    r['actor_transform']=tr(a.get_actor_transform())
    r['intent']=str(a.get_locomotion_input())
    r['simulation_mode']=str(a.get_simulation_mode())
    r['drag']=unreal.get_default_object(unreal.ProphecyAttackFootLocomotionLibrary).call_method('GetAttackFootLocomotion',(a,))
    for b in bones:
     i=next(i for i,n in enumerate(names) if str(n)==b)
     body=a.get_physical_body_state(b);target=a.get_authored_body_world_target(b)
     r['bones'][b]=dict(future=tr(future[i]),presented=tr(presented[i]),body=tr(body[0]) if body else None,target=tr(target[2]) if target else None)
     if body:r['bones'][b]['linear_velocity']=v(body[1]);r['bones'][b]['angular_velocity']=v(body[2])
    raw=a.get_locomotion_root_window()
    if raw:r['window']=[v(x.translation) for x in raw[0]]
    s['rows'].append(r)
   if clock==130:unreal.SystemLibrary.execute_console_command(world,'Prophecy.NNInputTraceFrames 90')
   if mode=='gaze_zero':a.set_upper_nn_gaze(0.,0.)
   if mode=='gaze_zero_late' and clock>=197:a.set_upper_nn_gaze(0.,0.)
   if mode=='kinematic' and clock==2:a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
   if mode=='kinematic_late' and clock>=210 and a.get_simulation_mode()!=unreal.ProphecyAgentSimulationMode.KINEMATIC:a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
   if mode=='no_feedback' and clock>=210:
    a.cancel_physical_feedback_tolerance_blend()
    a.set_all_physical_feedback_tolerances(1000000.,180.)
   if mode=='return_off' and clock==195:
    unreal.get_default_object(unreal.ProphecyFKReturnLibrary).call_method('SetAttackFKReturn',(a,False,1.,0.))
   if mode=='later_turn_stop' and clock>=210:
    intent=a.get_locomotion_input()
    if clock==210:
     f=intent.facing_world_direction;s['later_facing']=unreal.Vector((f.x+f.y)*.7071067811865476,(f.y-f.x)*.7071067811865476,0.)
    a.set_locomotion_input(intent.world_move_input,intent.run,s['later_facing'],intent.speed_scale,intent.turn_scale)
   if mode=='no_lower_tempering' and clock>=180:
    unreal.get_default_object(unreal.ProphecyLowerTemperingLibrary).call_method('SetLocomotionLowerBodyTempering',(a,False,1.,1.,1.,1.,1.,1.))
    unreal.get_default_object(unreal.ProphecyLegChainDebugLibrary).call_method('SetLegReconstructionRecovery',(a,0.,90.))
   if mode=='core_off' and clock==504:
    unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyAttackStartInertiaLibrary')).call_method('SetAttackStartFKCoreInertia',(a,False,.1,.3,.25,1.,1.))
   if mode=='pelvis_off' and clock==504:
    unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyAttackStartInertiaLibrary')).call_method('SetAttackStartPelvisInertia',(a,False,19,1.,10,1.))
   if mode=='sync_kinematic' and clock==160:a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
   if mode=='sync_physical_nn_seed_off' and clock==168:
    unreal.get_default_object(unreal.ProphecySpecialStartLibrary).call_method('SetSpecialStartFromPhysical',(a,False))
  if s['frames']>=310:finish('Complete')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
if s['owned']:level.editor_request_begin_play()
print('HEAD_ENTRY_STARTED',mode,'owned',s['owned'])
