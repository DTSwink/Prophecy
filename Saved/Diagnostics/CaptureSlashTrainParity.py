import unreal,builtins,pathlib,json,time,traceback,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
label=sys.argv[1] if len(sys.argv)>1 else 'baseline'
late_fix=False
trace=folder/'SlashContacts/live_steps.jsonl'
offset=trace.stat().st_size if trace.exists() else 0
s=dict(rows=[],last=None,wall=time.monotonic(),done=False)
builtins._slash_train_feet=s
bones=json.loads((pathlib.Path(unreal.Paths.project_dir())/'Tools/NN/Fixtures/SlashTrain2026092223.json').read_text())['initial_history']['bone_names']
def tr(x):return dict(p=[x.translation.x,x.translation.y,x.translation.z],q=[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w])
def finish(reason):
 if s['done']:return
 s['done']=True
 unreal.unregister_slate_post_tick_callback(s['cb'])
 unreal.SystemLibrary.execute_console_command(ed.get_game_world() or ed.get_editor_world(),'Prophecy.SlashTraceFrames 0')
 unreal.SystemLibrary.execute_console_command(ed.get_game_world() or ed.get_editor_world(),'Prophecy.SlashTraceAgent -1')
 if label!='baseline':unreal.SystemLibrary.execute_console_command(ed.get_game_world() or ed.get_editor_world(),'Prophecy.RootTranslation.CachedPoseRebase 1')
 (folder/f'SlashTrainParity-{label}.json').write_text(json.dumps(dict(reason=reason,rows=s['rows']),separators=(',',':')))
 if trace.exists():
  with trace.open('rb') as f:f.seek(offset);(folder/f'SlashTrainParity-{label}-nn.jsonl').write_bytes(f.read())
 if ed.get_game_world():unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
 print('SLASH_TRAIN_FEET_DONE',label,reason,len(s['rows']))
 s['rows'].clear()
def tick(_):
 try:
  w=ed.get_game_world()
  if not w:
   if s['rows'] or time.monotonic()-s['wall']>45:finish('World ended or unavailable')
   return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:
   if time.monotonic()-s['wall']>90:finish('Paused timeout')
   return
  s['last']=t
  for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
   if not a.is_player_controlled():continue
   state=a.get_nn_attack_state()
   r=dict(t=t,tick=int(a.get_editor_property('tick debug')),index=int(a.get_editor_property('Codex Slash Train Index')),attack=[str(state[0]),*state[1:]] if state else None,mode=str(a.get_simulation_mode()),root=tr(a.get_actor_transform()),meshes={},targets={})
   if label.startswith('raw') and r['tick']>=5 and not s.get('rolls_set'):
    roll=unreal.load_object(None,'/Script/GameAnimationSample3.Default__ProphecySpecialRollLibrary')
    assert roll.call_method('SetSpecialForearmRollCorrection',args=(a,label=='rawcalf'))
    assert roll.call_method('SetSpecialCalfRollCorrection',args=(a,label=='rawforearm'))
    if label=='rawattackviewer':
     interpolation=unreal.get_type_from_enum(unreal.load_object(None,'/Script/GameAnimationSample3.EProphecyNNInterpolationMode'))
     a.set_nn_interpolation_mode(interpolation.ATTACK_VIEWER)
     assert a.get_nn_interpolation_mode()==interpolation.ATTACK_VIEWER
    s['rolls_set']=True
   if label=='expiry' and r['tick']==950:
    assert r['index']==30
    assert a.trigger_nn_attack('jabL',a.get_actor_location()+unreal.Vector(100,30,70),False,None)
   for m in a.get_components_by_class(unreal.SkeletalMeshComponent):
    r['meshes'][m.get_name()]={b:tr(m.get_socket_transform(b,unreal.RelativeTransformSpace.RTS_WORLD)) for b in bones if m.get_bone_index(b)>=0}
   for b in bones:
    target=a.get_authored_body_world_target(b)
    if target:r['targets'][b]=dict(previous=tr(target[0]),future=tr(target[1]),target=tr(target[2]),alpha=target[3])
   s['rows'].append(r)
   if late_fix and r['tick']==147:unreal.SystemLibrary.execute_console_command(w,'Prophecy.RootTranslation.CachedPoseRebase 1')
   if r['tick']>=1050:finish('Complete');return
  if time.monotonic()-s['wall']>300:finish('Timeout')
 except Exception:finish(traceback.format_exc())
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.SlashTraceAgent -2')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.SlashTraceFrames 1200')
if label!='baseline':unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.RootTranslation.CachedPoseRebase '+('0' if late_fix else '1'))
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('SLASH_TRAIN_FEET_STARTED',label)
