import unreal,pathlib,json,time,math,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
owned=not bool(ed.get_game_world())
folder=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/WristArmedOrder20260930')
s=dict(start=time.monotonic(),n=0,last=None,rows=[])
def bend(hand,elbow):
 q=hand.rotation;x,y,z,w=q.x,q.y,q.z,q.w
 axis=(1-2*(y*y+z*z),2*(x*y+w*z),2*(x*z-w*y))
 v=hand.translation-elbow.translation;l=math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)
 return math.degrees(math.acos(max(-1,min(1,sum(a*b for a,b in zip(axis,(v.x/l,v.y/l,v.z/l)))))))
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 (folder/'current.json').write_text(json.dumps(dict(error=error,owned=owned,rows=s['rows']),indent=2),encoding='utf-8')
 if owned and ed.get_game_world():level.editor_request_end_play()
 print('WRIST_ORDER_DONE',error or 'complete',len(s['rows']))
def tick(_):
 try:
  if time.monotonic()-s['start']>60:finish('timeout');return
  w=ed.get_game_world()
  if not w:
   if s['n']:finish('play ended')
   return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t;s['n']+=1
  a=unreal.GameplayStatics.get_player_pawn(w,0)
  if isinstance(a,unreal.ProphecyAgent):
   data=a.read_nn_future_world_pose()
   if data:
    names,future,presented,alpha=data;names=[str(n) for n in names]
    h=names.index('hand_l');e=names.index('lowerarm_l')
    s['rows'].append(dict(n=s['n'],tick=int(a.get_editor_property('tick debug')),future=bend(future[h],future[e]),presented=bend(presented[h],presented[e]),attack=str(a.get_nn_attack_state()),mode=str(a.get_simulation_mode())))
  if s['n']>=300:finish()
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
if owned:level.editor_request_begin_play()
print('WRIST_ORDER_STARTED',owned)
