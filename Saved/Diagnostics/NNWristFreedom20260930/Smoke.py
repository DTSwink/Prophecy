import unreal, math, json, pathlib, time, traceback, builtins
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user Play'
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/NNWristFreedom20260930'
u=json.loads((pathlib.Path(unreal.Paths.project_content_dir())/'locomotion/NN/prophecy_upper_body_runtime.json').read_text())
lengths=[x[1]*100 for x in u['arm_limb_lengths_m']]
library=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyAttackWristLibrary'))
s=dict(last=None,frames=0,phase=-1,rows=[],wall=time.monotonic())
builtins._nn_wrist_freedom_smoke=s
def xyz(v):return [v.x,v.y,v.z]
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 (folder/'Smoke.json').write_text(json.dumps(dict(reason=reason,rows=s['rows'])))
 level.editor_request_end_play()
 print('NN_WRIST_FREEDOM_SMOKE_DONE',reason,len(s['rows']))
def tick(_):
 try:
  w=ed.get_game_world()
  if time.monotonic()-s['wall']>120:finish('Timeout');return
  if not w:return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t;s['frames']+=1
  for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
   if not a.is_player_controlled():continue
   frame=int(a.get_editor_property('tick debug'))
   phase=0 if frame<130 else 1 if frame<140 else 2 if frame<210 else 3
   if phase!=s['phase']:
    assert library.call_method('SetNNWristFreedom',(a,phase in (1,2),phase==2))
    s['phase']=phase
   pose=a.read_nn_future_world_pose()
   if not pose:continue
   names,future,shown,alpha=pose;idx={str(n):i for i,n in enumerate(names)}
   if 'hand_l' not in idx:continue
   errors=[abs(math.dist(xyz(future[idx['hand_'+side]].translation),xyz(future[idx['lowerarm_'+side]].translation))-lengths[i]) for i,side in enumerate(['l','r'])]
   assert all(math.isfinite(e) for e in errors)
   if frame>=216:assert max(errors)<0.001,('reattachment',frame,errors)
   s['rows'].append(dict(frame=frame,phase=phase,errors=errors,attack=str(a.get_nn_attack_state())))
  if s['frames']>=260:
   assert any(max(r['errors'])>.05 for r in s['rows'] if r['phase']==2),'Free-position NN still appears clamped'
   finish('Complete')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('NN_WRIST_FREEDOM_SMOKE_STARTED')
