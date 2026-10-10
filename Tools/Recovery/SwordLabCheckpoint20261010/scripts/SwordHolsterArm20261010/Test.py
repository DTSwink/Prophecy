import unreal,pathlib,time,json,traceback,re
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SwordHolsterArm20261010'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'User Play active'
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySwordHolsterLibrary'))
limb=unreal.ProphecyLimbCollisionLibrary
channels=[getattr(unreal.CollisionChannel,n) for n in dir(unreal.CollisionChannel) if n.startswith('ECC_') and 0<=getattr(unreal.CollisionChannel,n).value<32]
right=['upperarm_r','lowerarm_r','hand_r'];left=['upperarm_l','lowerarm_l','hand_l','spine_03']
s={'world':None,'start':time.monotonic(),'last':None,'events':[],'phases':set(),'draw':False,'complete':False,'checks':0}
def filters(a,bones):
 result={}
 for bone in bones:
  result[bone]={}
  for c in channels:
   v=limb.get_jolt_limb_collision_response(a,bone,c)
   assert v is not None,(bone,c)
   result[bone][str(c)]=[str(v[0]),str(v[1])]
 return result
def off(a):
 f=filters(a,right)
 for bone,values in f.items():
  for c,v in values.items():assert v[1]==str(unreal.CollisionResponseType.ECR_IGNORE),(bone,c,v)
 s['checks']+=1
 assert filters(a,left)==s['left'],'Unrelated collision changed'
def restored(a):
 assert filters(a,right)==s['expected'],'Right arm collision not restored'
 assert filters(a,left)==s['left'],'Unrelated collision changed'
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 result={k:v for k,v in s.items() if k not in ['cb','world','start','phases']};result['phases']=sorted(s['phases']);result['reason']=reason
 (out/'test.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
 if s['world'] and ed.get_game_world()==s['world']:level.editor_request_end_play()
 print('HOLSTER_ARM_TEST_FINISHED',reason)
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
  if n==s['last']:return
  s['last']=n
  if n==26:a.hide_sword();assert a.equip_sword(True)
  if n==28:
   s['expected']=filters(a,right);s['left']=filters(a,left)
   assert limb.set_jolt_limb_collision_response(a,'lowerarm_r',unreal.CollisionChannel.ECC_VEHICLE,unreal.CollisionResponseType.ECR_IGNORE,False) is not None
   assert api.call_method('SetSwordHolsterProfile',args=(a,70.,.25))
   assert api.call_method('DrawSword',args=(a,True,100.,180.,60.))
   off(a);s['events'].append([n,'sheath immediate suppression'])
  if n<29:return
  unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.HolsterReport')
  b=(out.parent/'SwordDraw20261010/state.txt').read_bytes();t=b.decode('utf-16' if b.startswith(b'\xff\xfe') else 'utf-8-sig')
  row=next(x for x in t.splitlines() if x.startswith(a.get_name()+' '));phase=int(re.search(r'phase=(-?\d+)',row)[1]);s['phases'].add(phase)
  if phase in [0,1,2,4]:off(a)
  if n==40:
   assert limb.set_jolt_limb_collision_response(a,'upperarm_r',unreal.CollisionChannel.ECC_VEHICLE,unreal.CollisionResponseType.ECR_IGNORE,False) is not None
   s['expected']['upperarm_r'][str(unreal.CollisionChannel.ECC_VEHICLE)][1]=str(unreal.CollisionResponseType.ECR_IGNORE)
   assert limb.reset_jolt_limb_collision(a,'lowerarm_r',False) is not None
   off(a)
   for i in range(3):assert api.call_method('DrawSword',args=(a,True,100.,180.,60.))
   s['events'].append([n,'configure/reset while suppressed and duplicate calls'])
  if phase==3 and not s['draw']:
   restored(a);s['events'].append([n,'sheathed collision restored'])
   assert api.call_method('DrawSword',args=(a,False,100.,180.,60.));s['draw']=True;off(a)
  if s['draw'] and phase==-1 and not s['complete']:
   restored(a);s['events'].append([n,'draw completed collision restored'])
   assert api.call_method('DrawSword',args=(a,True,100.,180.,60.));off(a)
   s['complete']=True;s['interrupt_at']=n+8
  if s['complete'] and n>=s['interrupt_at']:
   off(a);a.hide_sword();restored(a);s['events'].append([n,'hide interruption collision restored'])
   assert {1,2,3,4,-1}.issubset(s['phases'])
   finish('passed');return
  if n>600:finish('cycle incomplete')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('HOLSTER_ARM_TEST_STARTED',len(channels),'channels')
