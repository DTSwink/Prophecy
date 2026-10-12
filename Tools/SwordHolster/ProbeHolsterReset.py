"""Bounded owned-PIE reset drift probe. No editor asset writes."""
import argparse,json,pathlib,time,traceback,unreal
p=argparse.ArgumentParser();p.add_argument('--name',default='before');p.add_argument('--kinematic',action='store_true');args=p.parse_args()
out=pathlib.Path(unreal.Paths.project_dir())/'Saved/Diagnostics/HolsterReset20261012';out.mkdir(parents=True,exist_ok=True)
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'User Play left untouched'
state=dict(world=None,start=time.monotonic(),last=-1,rows=[],events=[])
def pose(t):
 p,q=t.translation,t.rotation
 return [p.x,p.y,p.z,q.x,q.y,q.z,q.w]
def finish(reason):
 unreal.unregister_slate_post_tick_callback(state['callback'])
 if state['world'] and ed.get_game_world()==state['world']:level.editor_request_end_play()
 (out/(args.name+'.json')).write_text(json.dumps(dict(reason=reason,rows=state['rows'],events=state['events']),separators=(',',':')),encoding='utf-8')
 print('HOLSTER_RESET_PROBE',reason)
def tick(_):
 try:
  if time.monotonic()-state['start']>120:return finish('timeout')
  w=ed.get_game_world()
  if not w:
   if state['world']:finish('world ended externally')
   return
  state['world']=w
  a=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(a,unreal.ProphecyAgent):return
  n=int(a.get_editor_property('absolute tick debug'))
  if n==state['last']:return
  state['last']=n
  actors=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
  if n==6:
   if args.kinematic:
    for actor in actors:assert actor.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
   state['events'].append([n,'init',str(unreal.ProphecyAgentResetLibrary.initialize_agent_reset(w))])
  row=dict(tick=n,actors={})
  for actor in actors:
   mesh=actor.get_pose_reference_mesh();pelvis=mesh.get_socket_transform('pelvis')
   components={}
   for c in actor.get_components_by_class(unreal.StaticMeshComponent):
    components[c.get_name()]=dict(world=pose(c.get_world_transform()),local=pose(unreal.MathLibrary.make_relative_transform(c.get_world_transform(),pelvis)),parent=str(c.get_attach_parent()),socket=str(c.get_attach_socket_name()))
   row['actors'][actor.get_name()]=dict(root=pose(actor.get_actor_transform()),pelvis=pose(pelvis),mode=str(actor.get_simulation_mode()),components=components)
  state['rows'].append(row)
  if n in [80,120,160,200,240]:state['events'].append([n,'reset',str(unreal.ProphecyAgentResetLibrary.reset_initial_agents(w))])
  if n>=270:finish('captured')
 except Exception:finish(traceback.format_exc())
state['callback']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
