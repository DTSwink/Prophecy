"""Owned, tick-indexed cross-family gameplay comparison; no saved asset changes."""
import unreal,pathlib,time,json,traceback,math
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
root=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/AttackPerformance20261002'
mode=int((root/'motion_mode.txt').read_text(encoding='utf8'))
tag='motion_native' if mode else 'motion_original'
for cmd in ('Prophecy.Attack.NativeGeometry '+str(mode),'Prophecy.Editor.ClearAttackCache'):
 unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),cmd)
families=['slashL','slashR','slashLU','slashRU','slashLD','slashRD','pike','jabL','jabR','hookL','hookR','overL','overR','headbutt','kickL','kickR']
s=dict(start=time.monotonic(),world=None,last=None,frame=0,actors=[],rows=[],events=[])
def tr(t):return [t.translation.x,t.translation.y,t.translation.z,t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w]
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 w=ed.get_game_world()
 (root/(tag+'.json')).write_text(json.dumps(dict(reason=reason,frames=s['frame'],events=s['events'],rows=s['rows']),separators=(',',':')),encoding='utf8')
 target=w or ed.get_editor_world()
 unreal.SystemLibrary.execute_console_command(target,'Prophecy.Attack.NativeGeometry 1')
 unreal.SystemLibrary.execute_console_command(target,'Prophecy.Editor.ClearAttackCache')
 if w is not None and w==s['world']:level.editor_request_end_play()
 print('ATTACK_MOTION_DONE',tag,reason,s['frame'])
def tick(dt):
 try:
  if time.monotonic()-s['start']>150:finish('Watchdog');return
  w=ed.get_game_world()
  if w is None:
   if s['world'] is not None:finish('World ended')
   return
  if s['world'] is None:s['world']=w
  elif s['world']!=w:finish('World replaced');return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if s['last']==t:return
  s['last']=t;s['frame']+=1;f=s['frame']
  if f==30:
   s['actors']=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
   s['player']=unreal.GameplayStatics.get_player_pawn(w,0)
   for a in s['actors']:
    a.set_actor_tick_enabled(False);a.stop_nn_attack();a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
  if not s['actors']:return
  for actor in s['actors']:actor.apply_nn_pose_kinematically(dt)
  case=(f-60)//80;offset=(f-60)%80
  if 0<=case<len(families):
   a=s['player']
   if offset==0:
    a.stop_nn_attack()
    names,pose,_,_=a.read_nn_future_world_pose();pelvis=pose[[str(n) for n in names].index('pelvis')].translation
    target=pelvis+unreal.Vector(-30,90,30)
    half=bool(case%2) and not families[case].startswith('kick')
    ok=a.trigger_nn_attack(families[case],target,half)
    s['events'].append(dict(frame=f,family=families[case],half=half,ok=ok))
    assert ok,families[case]
   if offset==60:a.stop_nn_attack()
   names,future,presented,alpha=a.read_nn_future_world_pose()
   values=[tr(v) for v in future];assert all(math.isfinite(x) for row in values for x in row)
   s['rows'].append(dict(frame=f,state=str(a.get_nn_attack_state()),future=values,presented=[tr(v) for v in presented]))
  if f>=1341:finish('Complete')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('ATTACK_MOTION_STARTED',tag)
