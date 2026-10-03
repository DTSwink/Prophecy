import unreal,time,json,pathlib,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
folder=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics')
s=dict(start=time.monotonic(),world=None,rows=[],phase=-1)
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 if ed.get_game_world() and ed.get_game_world()==s['world']:level.editor_request_end_play()
 (folder/'PotRopeConvergence.json').write_text(json.dumps(dict(error=error,samples=s['rows']),indent=2))
def tick(_):
 try:
  w=ed.get_game_world()
  if not w:
   if time.monotonic()-s['start']>40:finish('No PIE')
   return
  if s['world'] is None:s['world']=w
  if w!=s['world']:finish('World replaced');return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t<.1:return
  phase=min(int(t/3),3)
  if phase!=s['phase']:
   unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.SkeletonAudit '+['0 0','0 0','10 32','40 64'][phase])
   if phase==1:
    for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor):
     if a.get_class().get_name()=='A_Pot_C': a.get_component_by_class(unreal.PhysicsConstraintComponent).set_disable_collision(True)
   s['phase']=phase
  if s['rows'] and t<s['rows'][-1]['time']+.15:return
  unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.SkeletonAudit')
  unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.ConstraintAudit A_Pot')
  skel=json.loads((folder/'ConstrainedSkeleton.json').read_text(encoding='utf-8-sig'))
  joint=json.loads((folder/'StandardConstraints/World.json').read_text(encoding='utf-8-sig'))
  s['rows'].append(dict(time=t,phase=phase,skeleton=skel,joint=joint))
  if t>=12:finish()
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
