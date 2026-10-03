import unreal,pathlib,json,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user PIE'
p=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/GhostEnd')
log=pathlib.Path(unreal.Paths.project_log_dir(),'GameAnimationSample3.log');offset=log.stat().st_size
families=['hookL','hookR','overL','overR','pike','jabL','slashLU']
s=dict(start=time.monotonic(),last=None,n=0,a=None,case=-1,active=False,wait=0,rows=[],events=[])
def cmd(v):unreal.SystemLibrary.execute_console_command(ed.get_game_world() or ed.get_editor_world(),v)
cmd('Prophecy.AttackEndExtension.Audit 1')
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb']);cmd('Prophecy.AttackEndExtension.Audit 0')
 (p/'families.json').write_text(json.dumps(dict(error=error,events=s['events'],rows=s['rows'])))
 with log.open('rb') as f:f.seek(offset);(p/'families.log').write_bytes(f.read())
 if ed.get_game_world():level.editor_request_end_play()
 print('END_EXTENSION_FAMILIES_DONE',error or 'complete')
def tick(_):
 try:
  if time.monotonic()-s['start']>100:finish('timeout');return
  w=ed.get_game_world()
  if not w:return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t;s['n']+=1
  if s['n']<100:return
  if not s['a']:
   a=next(a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent) if a.is_player_controlled());s['a']=a
   a.set_actor_tick_enabled(False);a.stop_nn_attack()
   lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyAttackEndExtensionLibrary'))
   assert lib.call_method('SetAttackEndExtension',(a,True,0.,0.,0.))
   assert not lib.call_method('SetAttackEndExtension',(a,True,-1.,0.,0.))
   assert not lib.call_method('SetAttackEndExtension',(a,True,0.,181.,0.))
  a=s['a'];state=a.get_nn_attack_state()
  if s['active']:
   s['rows'].append(dict(case=s['case'],tick=s['n'],time=t,state=str(state)))
   if not state:s['active']=False;s['wait']=s['n']+8
  elif s['n']>=s['wait']:
   s['case']+=1
   if s['case']>=len(families):finish();return
   family=families[s['case']]
   # Keep the Blueprint's authored trims: hook/over two ticks, slashLU one tick.
   target=a.get_root_low_point()+unreal.Vector(-30,50,115)
   assert a.trigger_nn_attack(family,target,True)
   s['events'].append(dict(case=s['case'],family=family,tick=s['n'],time=t));s['active']=True
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
print('END_EXTENSION_FAMILIES_STARTED')
