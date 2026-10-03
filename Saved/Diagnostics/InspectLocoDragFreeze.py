import unreal, pathlib, json, time, traceback, math
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world()
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/LocoDragFreeze20261002'
p.mkdir(exist_ok=True)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
(p/'graph-before.txt').write_bytes((p.parent/'SwordThigh/BlueprintGraph.txt').read_bytes())
s=dict(start=time.monotonic(),world=w,last=None,rows=[])
def v(x): return [x.x,x.y,x.z]
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 (p/'passive.json').write_text(json.dumps(dict(reason=reason,rows=s['rows'])),encoding='utf8')
 print('PASSIVE_LOCO_FREEZE_DONE',reason,len(s['rows']))
def tick(_):
 try:
  if ed.get_game_world()!=s['world'] or s['world'] is None: finish('No original Play');return
  if time.monotonic()-s['start']>10: finish('Complete');return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t
  a=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(a,unreal.ProphecyAgent):return
  mask=unreal.get_default_object(unreal.ProphecyAttackFootLocomotionLibrary).call_method('GetAttackFootLocomotion',(a,))
  r=dict(tick=a.get_editor_property('tick debug'),attack=str(a.get_nn_attack_state()),mask=mask)
  if any(mask):
   raw=a.get_locomotion_root_window()
   continuous=unreal.ProphecyRootPhysicsLibrary.get_continuous_locomotion_root_window(a)
   pose=a.read_nn_future_world_pose()
   r.update(raw=[v(x.translation) for x in raw[0]] if raw else [],continuous=[v(x.translation) for x in continuous[0]] if continuous else [],pelvis=v(pose[2][0].translation))
  s['rows'].append(r)
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
print('PASSIVE_LOCO_FREEZE_STARTED',bool(w))
