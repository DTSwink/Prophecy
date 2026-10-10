import unreal,pathlib,time,json,traceback,re,math,shutil
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SwordStall20261010'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
w=ed.get_game_world();s={'owned':not bool(w),'world':w,'start':time.monotonic(),'last':None,'rows':[]}
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
shutil.copy2(out.parent/'SwordThigh/BlueprintGraph.txt',out/'graph.txt')
def vec(v):return [v.x,v.y,v.z]
def dist(a,b):return math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 result={k:v for k,v in s.items() if k not in ['cb','world','start']};result['reason']=reason
 (out/'probe.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
 if s['owned'] and s['world'] and ed.get_game_world()==s['world']:level.editor_request_end_play()
 print('SWORD_STALL_PROBE_FINISHED',reason,'owned',s['owned'])
def tick(_):
 try:
  if time.monotonic()-s['start']>15:finish('capture complete');return
  w=ed.get_game_world()
  if not w:
   if s['world']:finish('world ended')
   return
  s['world']=w;a=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(a,unreal.ProphecyAgent):return
  n=int(a.get_editor_property('absolute tick debug'))
  if s['last'] is not None and n-s['last']<5:return
  s['last']=n
  unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.HolsterReport')
  b=(out.parent/'SwordDraw20261010/state.txt').read_bytes();txt=b.decode('utf-16' if b.startswith(b'\xff\xfe') else 'utf-8-sig')
  state=next((x for x in txt.splitlines() if x.startswith(a.get_name()+' ')),'')
  bones=['upperarm_r','lowerarm_r','hand_r','clavicle_r','pelvis']
  m=a.get_pose_reference_mesh();physical={b:vec(m.get_socket_location(b)) for b in bones}
  names,future,presented,alpha=a.read_nn_future_world_pose()
  nn={str(k):vec(t.translation) for k,t in zip(names,presented) if str(k) in bones}
  r={'tick':n,'state':state,'physical':physical,'nn':nn,'alpha':alpha}
  match=re.search(r'goal=X=([-\d.]+) Y=([-\d.]+) Z=([-\d.]+)',state)
  if match and all(b in nn for b in bones):
   goal=[float(x) for x in match.groups()];r['goal']=goal
   for label,p in [('physical',physical),('nn',nn)]:
    l1=dist(p['upperarm_r'],p['lowerarm_r']);l2=dist(p['lowerarm_r'],p['hand_r']);d=dist(p['upperarm_r'],goal)
    r[label+'_metrics']={'arm_length':l1+l2,'shoulder_target':d,'reach_shortfall':d-l1-l2,'hand_target_error':dist(p['hand_r'],goal),'shoulder_hand':dist(p['upperarm_r'],p['hand_r'])}
   r['physical_nn_hand_error']=dist(physical['hand_r'],nn['hand_r'])
  r['collision']={b:str(unreal.ProphecyLimbCollisionLibrary.get_jolt_limb_collision_response(a,b,unreal.CollisionChannel.ECC_PHYSICS_BODY)) for b in bones[:3]}
  s['rows'].append(r)
  if s['owned'] and n>=220:finish('through tick220')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
if s['owned']:level.editor_request_begin_play()
print('SWORD_STALL_PROBE_STARTED','owned',s['owned'])
