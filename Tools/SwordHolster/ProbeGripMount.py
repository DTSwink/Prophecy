"""Owned PIE: stabilize, interrupt, and check the exact authored local mount."""
import argparse, json, pathlib, re, time, traceback, unreal
p=argparse.ArgumentParser()
p.add_argument('--action',choices=['hide','drop','mode','reset'],required=True)
p.add_argument('--phase',type=int,choices=[2,5],default=5)
p.add_argument('--output',default='Saved/Diagnostics/TipAlignPort20261013/lifecycle')
args=p.parse_args()
root=pathlib.Path(unreal.Paths.project_dir());out=root/args.output;out.mkdir(parents=True,exist_ok=True)
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Existing user Play left untouched'
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySwordHolsterLibrary'))
s={'world':None,'start':time.monotonic(),'last':-1,'events':[]}
def pose(t):
 q=t.rotation;p=t.translation;return [p.x,p.y,p.z,q.x,q.y,q.z,q.w]
def limits(mesh):
 lib=unreal.ConstraintInstanceBlueprintLibrary
 return sorted([[str(x) for x in lib.get_attached_body_names(c)[1:]]+[str(lib.get_angular_limits(c)[1:])] for c in mesh.get_constraints(True)])

def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['callback'])
 if s['world'] and ed.get_game_world()==s['world']:level.editor_request_end_play()
 result={k:v for k,v in s.items() if k not in ['world','start','callback','neutral','holster','sword']}
 result['reason']=reason;result['options']=vars(args)
 (out/f'{args.action}-{args.phase}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
 print('GRIP_MOUNT_FINISHED',reason)
def tick(_):
 try:
  if time.monotonic()-s['start']>120:return finish('timeout')
  w=ed.get_game_world()
  if not w:
   if s['world']:finish('ended externally')
   return
  s['world']=w;a=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(a,unreal.ProphecyAgent):return
  n=int(a.get_editor_property('absolute tick debug'))
  if n==s['last']:return
  s['last']=n
  if n>=20 and 'neutral' not in s:
   s['holster']=next(c for c in a.get_components_by_class(unreal.StaticMeshComponent) if c.get_name()=='holster')
   s['neutral']=s['holster'].get_relative_transform();s['before']=pose(s['neutral']);a.hide_sword();s['limits_before']=limits(a.get_pose_reference_mesh())
  if n>=35 and not s.get('equipped'):
   assert a.equip_sword(True);s['equipped']=n
  if n>=40 and not s.get('started'):
   s['sword']=a.get_held_sword();assert s['sword']
   assert api.call_method('SetSwordHolsterLabProfile',args=(a,'Content/locomotion/SwordHolsterProfile.json'))
   assert api.call_method('SetSwordHolsterProfile',args=(a,25.,.5,100.,.5,.25,150.,200.,True,2.))
   if args.action=='reset':s['reset_init']=str(unreal.ProphecyAgentResetLibrary.initialize_agent_reset(w))
   assert api.call_method('DrawSword',args=(a,True,230.,600.,150.));s['started']=n
  if not s.get('started'):return
  unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.HolsterReport')
  raw=(root/'Saved/Diagnostics/SwordDraw20261010/state.txt').read_bytes();text=raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig')
  line=next(x for x in text.splitlines() if x.startswith(a.get_name()+' '))
  fields={k:float(v) for k,v in re.findall(r'(\w+)=(-?\d+(?:\.\d+)?)',line)}
  if s.get('interrupted') and n>s['interrupted']:
   s.setdefault('after_ticks',[]).append([n,fields])
   if fields['phase']==-1 and fields['joint']==0:
    assert limits(a.get_pose_reference_mesh())==s['limits_before'],'Limits not restored after tick boundary'
    s['cleanup_observed']=n
  if not s.get('interrupted') and fields['phase']==args.phase:
   assert s['holster'].get_editor_property('absolute_rotation'),'Stabilization did not activate'
   s['events'].append([n,'interrupt',fields]);s['interrupted']=n
   if args.action=='hide':a.hide_sword()
   elif args.action=='drop':
    before=s['sword'].get_editor_property('root_component').get_world_transform()
    dropped=a.drop_sword();assert dropped
    after=dropped.get_editor_property('root_component').get_world_transform();s['drop_before']=pose(before);s['drop_after']=pose(after)
    q,r=before.rotation,after.rotation
    assert (after.translation-before.translation).length()<.0001 and 1-abs(q.x*r.x+q.y*r.y+q.z*r.z+q.w*r.w)<1e-10,'Drop changed the sword world pose'
   elif args.action=='mode':assert a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
   elif args.action=='reset':s['reset']=str(unreal.ProphecyAgentResetLibrary.reset_initial_agents(w))
   unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.HolsterReport')
   raw=(root/'Saved/Diagnostics/SwordDraw20261010/state.txt').read_bytes();report=raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig')
   row=next(x for x in report.splitlines() if x.startswith(a.get_name()+' '))
   s['immediate_after']={k:float(v) for k,v in re.findall(r'(\w+)=(-?\d+(?:\.\d+)?)',row)}
   # Reset is queued for the next tick; mode transitions finish there too.
   if args.action!='reset':assert s['immediate_after']['joint']==0,s['immediate_after']
   if args.action not in ['mode','reset']:
    assert s['immediate_after']['phase']==-1,s['immediate_after']
    assert limits(a.get_pose_reference_mesh())==s['limits_before'],'Limits not restored at interruption'
  if s.get('interrupted') and n>=s['interrupted']+6:
   h=s['holster'];after=h.get_relative_transform();s['after']=pose(after);s['fields_after']=fields
   assert not h.get_editor_property('absolute_rotation'),'Rotation inheritance not restored'
   pos=(after.translation-s['neutral'].translation).length()
   q,r=after.rotation,s['neutral'].rotation;dot=abs(q.x*r.x+q.y*r.y+q.z*r.z+q.w*r.w)
   assert pos<.0001 and 1-dot<1e-10,('Mount changed',pos,dot)
   # The user's infinite Blueprint loop may issue a fresh kinematic request.
   restarted=args.action=='mode' and fields['kinematic']==1 and fields['phase']==1 and fields['pose_tick']<=6
   restarted |= args.action=='reset' and bool(s.get('cleanup_observed')) and fields['phase'] in [0,1] and fields['pose_tick']<=6
   s['blueprint_restarted']=restarted
   assert (fields['phase']==-1 or restarted) and fields['joint']==0,fields
   s['limits_after']=limits(a.get_pose_reference_mesh())
   if not restarted:assert s['limits_after']==s['limits_before'],'Joint angular limits not restored'
   elif args.action=='reset':assert s.get('cleanup_observed'),'No restored boundary before the new action'
   return finish('passed')
  if n>450:return finish('did not reach requested phase')
 except Exception:return finish(traceback.format_exc())
s['callback']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play();print('GRIP_MOUNT_STARTED',vars(args))
