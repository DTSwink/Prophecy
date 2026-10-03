import unreal,pathlib,json,time,traceback,math
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
owned=not bool(ed.get_game_world())
s=dict(start=time.monotonic(),last=None,n=0,rows=[])
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/LocoDragRootWindow.json').write_text(json.dumps(dict(error=error,rows=s['rows']),separators=(',',':')))
 if owned and ed.get_game_world():level.editor_request_end_play()
 print('LOCO_DRAG_ROOT_WINDOW',error or 'passed',len(s['rows']))
def tick(_):
 try:
  assert time.monotonic()-s['start']<65,'Timeout'
  w=ed.get_game_world()
  if not w:
   if s['n']:finish('User ended Play')
   return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if s['last']==t:return
  s['last']=t;s['n']+=1
  a=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(a,unreal.ProphecyAgent) or s['n']<20:return
  attack=a.get_nn_attack_state();full=bool(attack and not attack[1])
  owners=unreal.ProphecyAttackFootLocomotionLibrary.get_attack_foot_locomotion(a)
  result=unreal.ProphecyRootPhysicsLibrary.get_continuous_locomotion_root_window(a)
  error=0.;span=0.
  if full and not any(owners):assert result is None,('Completed full attack should reject',s['n'])
  else:
   assert result is not None,('Missing root window',s['n'],attack,owners)
   roots,times=result
   assert len(roots)==len(times)==9
   assert times[0]==0. and all(times[i]>times[i-1] for i in range(1,9))
   r=roots[0].translation;p=a.get_root_low_point()
   error=math.sqrt((r.x-p.x)**2+(r.y-p.y)**2+(r.z-p.z)**2)
   assert error<.001,(s['n'],error)
   yaw=(roots[0].rotation.rotator().yaw-a.get_actor_rotation().yaw+180)%360-180
   assert abs(yaw)<.001
   q=roots[1].translation;span=math.sqrt((r.x-q.x)**2+(r.y-q.y)**2+(r.z-q.z)**2)
  s['rows'].append(dict(tick=a.get_editor_property('tick debug'),full=full,owners=owners,valid=result is not None,error=error,span=span))
  if s['n']>=390:
   assert any(r['full'] and any(r['owners']) for r in s['rows']),'No loco drag observed'
   assert any(r['full'] and not any(r['owners']) for r in s['rows']),'No completed full attack observed'
   finish()
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
if owned:level.editor_request_begin_play()
