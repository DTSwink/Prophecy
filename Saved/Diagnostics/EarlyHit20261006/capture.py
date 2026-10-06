import unreal,json,pathlib,time,traceback,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/EarlyHit20261006'
mode=sys.argv[1] if len(sys.argv)>1 else 'baseline'
s={'world':None,'last':None,'start':time.monotonic(),'rows':[],'hits':[],'bindings':[],'agents':[],'errors':[]}
def v(x):return [x.x,x.y,x.z]
def tr(x):return {'p':v(x.translation),'q':[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w]}
def attack(a):
 r=a.get_nn_attack_state() if isinstance(a,unreal.ProphecyAgent) else None
 return [str(r[0]),*r[1:]] if r else None
def hit_event(comp,other,othercomp,impulse,hit):
 try:
  a=comp.get_owner();player=unreal.GameplayStatics.get_player_pawn(s['world'],0)
  r={'tick':int(player.get_editor_property('absolute tick debug')),'time':unreal.GameplayStatics.get_time_seconds(s['world']),'self':a.get_name(),'other':other.get_name() if other else None,'self_component':comp.get_name(),'other_component':othercomp.get_name() if othercomp else None,'impulse':v(impulse),'attack_self':attack(a),'attack_other':attack(other),'hit':{}}
  for name in ['location','impact_point','normal','impact_normal','bone_name','my_bone_name','time','distance','penetration_depth','blocking_hit','start_penetrating']:
   try:
    x=hit.get_editor_property(name);r['hit'][name]=v(x) if isinstance(x,unreal.Vector) else str(x) if isinstance(x,unreal.Name) else x
   except Exception:pass
  for label,agent,bone in [('self',a,r['hit'].get('my_bone_name','None')),('other',other,r['hit'].get('bone_name','None'))]:
   if isinstance(agent,unreal.ProphecyAgent) and bone!='None':
    state=agent.get_physical_body_state(bone)
    if state:r[label+'_body']={'transform':tr(state[0]),'v':v(state[1]),'w':v(state[2])}
  s['hits'].append(r)
 except Exception:s['errors'].append(traceback.format_exc())
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 if s['world'] is not None and ed.get_game_world()==s['world']:
  unreal.SystemLibrary.execute_console_command(s['world'],'Prophecy.Reset.HitAudit sample')
  audit=p.parent/'ResetHitAudit.json'
  if audit.exists():
   (p/(mode+'-hits.json')).write_bytes(audit.read_bytes())
  unreal.SystemLibrary.execute_console_command(s['world'],'Prophecy.Reset.HitAudit stop')
 for c in s['bindings']:
  try:c.on_component_hit.remove_callable(hit_event)
  except Exception:pass
 (p/(mode+'.json')).write_text(json.dumps({'reason':reason,'rows':s['rows'],'hits':s['hits'],'errors':s['errors']},separators=(',',':')),encoding='utf8')
 if s['world'] is not None and ed.get_game_world()==s['world']:level.editor_request_end_play()
 print('EARLY_HIT_DONE',mode,reason,len(s['hits']))
def tick(_):
 try:
  if time.monotonic()-s['start']>70:finish('timeout');return
  w=ed.get_game_world()
  if not w:
   if s['world'] is not None:finish('world ended')
   return
  if s['world'] is None:s['world']=w
  if w!=s['world']:finish('world replaced');return
  player=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(player,unreal.ProphecyAgent):return
  n=int(player.get_editor_property('absolute tick debug'))
  if n==s['last']:return
  s['last']=n
  if not s['agents']:
   s['agents']=list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent))
   unreal.SystemLibrary.execute_console_command(w,'Prophecy.Reset.HitAudit start')
  if mode.startswith('sweeps_off') and n>=(46 if mode=='sweeps_off_late' else 25):
   for a in s['agents']:assert unreal.ProphecyJoltPHATSweepLibrary.set_jolt_phat_sweeps(a,False)
  for a in s['agents']:
   if not a.has_valid_agent_handle():continue
   r={'tick':n,'time':unreal.GameplayStatics.get_time_seconds(w),'actor':a.get_name(),'player':a==player,'attack':attack(a),'sweeps':str(unreal.ProphecyJoltPHATSweepLibrary.get_jolt_phat_sweeps(a)),'bones':{}}
   for bone in ['head','neck_01','spine_03','spine_05','clavicle_l','upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r','pelvis']:
    b=a.get_physical_body_state(bone)
    if b:r['bones'][bone]={'transform':tr(b[0]),'v':v(b[1]),'w':v(b[2])}
   s['rows'].append(r)
  if n>=100:finish('complete')
 except Exception:finish(traceback.format_exc())
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
(p/(mode+'-graph.txt')).write_bytes((p.parent/'SwordThigh/BlueprintGraph.txt').read_bytes())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play();print('EARLY_HIT_STARTED',mode)
