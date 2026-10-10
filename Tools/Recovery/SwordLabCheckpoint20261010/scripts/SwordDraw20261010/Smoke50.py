import unreal,pathlib,time,json,traceback,math
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SwordDraw20261010'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'User Play active'
s={'world':None,'start':time.monotonic(),'last':None,'rows':[],'draw':False,'sword':None}
def read(p):
 b=p.read_bytes();return b.decode('utf-16' if b.startswith(b'\xff\xfe') else 'utf-8-sig')
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 (out/'smoke-50.json').write_text(json.dumps({'reason':reason,'rows':s['rows']},indent=2),encoding='utf-8')
 if s['world'] and ed.get_game_world()==s['world']:level.editor_request_end_play()
 print('HOLSTER_SMOKE_FINISHED',reason)
def tick(_):
 try:
  if time.monotonic()-s['start']>240:finish('timeout');return
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
  unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.HolsterReport')
  txt=read(out/'state.txt');row=next((x for x in txt.splitlines() if x.startswith(a.get_name()+' ')),'NO REFERENCE')
  scale=None
  if s['sword']:
   v=s['sword'].root_component.get_world_transform().scale3d;scale=[v.x,v.y,v.z]
  if n%5==0 or n in [24,25,26]:s['rows'].append({'tick':n,'state':row,'scale':scale,'held':bool(a.get_held_sword())})
  if n==24:
   assert scale is not None,'No equipped sword before requested branch'
   assert max(abs(x-y) for x,y in zip(scale,[.83772678,.766193508,1.311941499]))<.0001,('Double/wrong scale',scale)
  if n==26:
   a.hide_sword();assert a.equip_sword(True);s['sword']=a.get_held_sword()
  if n==28:
   api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySwordHolsterLibrary'))
   assert api.call_method('SetSwordHolsterProfile',args=(a,50.0,0.25))
   assert api.call_method('DrawSword',args=(a,True,100.0,180.0,60.0))
  if n>25 and 'phase=3' in row and not s['draw']:
   assert 'joint=0' in row and 'scale=0.500000' in row,row
   assert not a.get_held_sword()
   assert unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySwordHolsterLibrary')).call_method('DrawSword',args=(a,False,100.0,180.0,60.0))
   s['draw']=True;s['rows'].append({'tick':n,'event':'draw started'})
  if s['draw'] and 'phase=-1' in row:
   assert a.get_held_sword()==s['sword']
   assert max(abs(x-y) for x,y in zip(scale,[.83772678,.766193508,1.311941499]))<.0001,scale
   finish('passed');return
  if n>=550:finish('did not complete by tick550');return
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('HOLSTER_SMOKE_STARTED')


