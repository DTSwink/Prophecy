import unreal,pathlib,time,json,traceback,math,sys
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SwordHolsterFix20261010'
tag=sys.argv[1] if len(sys.argv)>1 else 'after'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'User Play active'
s={'world':None,'start':time.monotonic(),'last':None,'rows':[],'held_tick':None,'draw':False,'sword':None,'max_xy':0,'max_local_cm':0,'max_local_deg':0,'parent_motion':0,'min_z':1,'max_native_gap':0}
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySwordHolsterLibrary'))
def vec(v):return [v.x,v.y,v.z]
def dist(a,b):return math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))
def quat(q):return [q.x,q.y,q.z,q.w]
def angle(a,b):return math.degrees(2*math.acos(min(1,abs(sum(x*y for x,y in zip(a,b))))))
def read(p):
 b=p.read_bytes();return b.decode('utf-16' if b.startswith(b'\xff\xfe') else 'utf-8-sig')
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 result={k:v for k,v in s.items() if k not in ['world','sword','cb','start','relative','holster']};result['reason']=reason
 (out/(tag+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
 if s['world'] and ed.get_game_world()==s['world']:level.editor_request_end_play()
 print('SWORD_FIX_TEST_FINISHED',tag,reason)
def tick(_):
 try:
  if time.monotonic()-s['start']>180:finish('timeout');return
  w=ed.get_game_world()
  if not w:
   if s['world']:finish('world ended')
   return
  s['world']=w;a=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(a,unreal.ProphecyAgent):return
  n=int(a.get_editor_property('absolute tick debug'))
  if s['last']==n:return
  s['last']=n
  if not s['sword']:s['sword']=a.get_held_sword()
  if n==24:
   assert s['sword'];s['base_scale']=vec(s['sword'].root_component.get_world_transform().scale3d)
  if n==26:
   a.hide_sword();assert a.equip_sword(True);s['sword']=a.get_held_sword()
  if n==28:
   assert api.call_method('SetSwordHolsterProfile',args=(a,70.0,.25))
   assert api.call_method('DrawSword',args=(a,True,100.0,180.0,60.0))
  unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.HolsterReport')
  row=next((x for x in read(out.parent/'SwordDraw20261010/state.txt').splitlines() if x.startswith(a.get_name()+' ')),'no reference')
  if n<29:return
  sword=s['sword'].root_component;scale=vec(sword.get_world_transform().scale3d)
  s['max_xy']=max(s['max_xy'],max(abs(scale[i]/s['base_scale'][i]-1) for i in [0,1]))
  s['min_z']=min(s['min_z'],scale[2]/s['base_scale'][2])
  if n%10==0:s['rows'].append({'tick':n,'state':row,'scale':scale})
  if 'phase=3' in row and s['held_tick'] is None:
   h=next(c for c in a.get_components_by_class(unreal.SceneComponent) if c.get_name()=='holster')
   assert sword.get_attach_parent()==h,('wrong parent',sword.get_attach_parent())
   s['holster']=h;s['held_tick']=n;s['relative']=sword.get_relative_transform();s['parent_start']=vec(h.get_world_transform().translation)
  if s['held_tick'] is not None and not s['draw']:
   h=s['holster'];rel=sword.get_relative_transform()
   assert sword.get_attach_parent()==h,'lost holster parent'
   s['max_local_cm']=max(s['max_local_cm'],dist(vec(rel.translation),vec(s['relative'].translation)))
   s['max_local_deg']=max(s['max_local_deg'],angle(quat(rel.rotation),quat(s['relative'].rotation)))
   s['parent_motion']=max(s['parent_motion'],dist(vec(h.get_world_transform().translation),s['parent_start']))
   native=a.get_physical_body_state('sword')
   assert native and not native[3],'holstered sword must remain a managed kinematic body'
   s['max_native_gap']=max(s['max_native_gap'],dist(vec(native[0].translation),vec(sword.get_world_transform().translation)))
   elapsed=n-s['held_tick']
   # Give the real mover translation and turning intent; never alter saved Blueprint values.
   a.set_locomotion_input(unreal.Vector(1,0,0),False,unreal.Vector(1,.5,0),1,1)
   if elapsed<60:
    # A controlled additional parent displacement exercises the attachment across
    # physics publication even when the user's Tick logic overwrites movement input.
    t=h.get_world_transform();t.translation=t.translation+unreal.Vector(2,0,0)
    h.set_world_transform(t,False,True)
   else:
    a.stop_locomotion_input()
    assert api.call_method('DrawSword',args=(a,False,100.0,180.0,60.0));s['draw']=True
    s['rows'].append({'tick':n,'event':'draw after moving holster'})
  if s['draw'] and 'phase=-1' in row:
   assert a.get_held_sword()==s['sword']
   assert dist(scale,s['base_scale'])<.0001,('restored scale',scale)
   if tag!='before':
    assert s['max_xy']<.00001,('width/thickness changed',s['max_xy'])
    assert abs(s['min_z']-.3)<.0001,('blade length',s['min_z'])
    assert s['max_local_cm']<.001 and s['max_local_deg']<.001,('holster offset drift',s['max_local_cm'],s['max_local_deg'])
    assert s['max_native_gap']<10,('native body not following receiver',s['max_native_gap'])
    assert s['parent_motion']>5,('movement test ineffective',s['parent_motion'])
   finish('passed' if tag!='before' else 'baseline captured');return
  if n>=600:finish('cycle incomplete');return
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('SWORD_FIX_TEST_STARTED',tag)

