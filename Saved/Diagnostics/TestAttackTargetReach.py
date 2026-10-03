import unreal,time,json,pathlib,traceback,math
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyAttackControlLibrary'))
data=json.loads((pathlib.Path(unreal.Paths.project_dir())/'Docs/AttackTargetReach.json').read_text())
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/AttackTargetReachPIE.json'
s=dict(start=time.monotonic(),world=None)
order=('slashL','slashR','slashLD','slashRD','slashLU','slashRU','pike','jabL','jabR','hookL','hookR','overL','overR','headbutt','kickL','kickR')
V=unreal.Vector
def call(n,*args):return api.call_method(n,tuple(args))
def finish(result):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 if ed.get_game_world() and ed.get_game_world()==s['world']:level.editor_request_end_play()
 out.write_text(json.dumps(result,indent=2));print('ATTACK_TARGET_REACH',result)
def tick(_):
 try:
  w=ed.get_game_world()
  if not w:
   if time.monotonic()-s['start']>35:finish(dict(error='No PIE world'))
   return
  if s['world'] is None:s['world']=w
  if w!=s['world']:finish(dict(error='Play session replaced'));return
  if unreal.GameplayStatics.get_time_seconds(w)<.8:return
  actors=[a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent) if a.has_valid_agent_handle()]
  assert len(actors)>=2
  a,b=actors[:2]
  assert call('SetAttackTargetExtraReach',a,*([50.]*16))
  assert call('SetAttackTargetExtraReach',b,*([50.]*16))
  # Same foot-source rules as native balancing; the current setup is kinematic.
  assert a.get_simulation_mode()==unreal.ProphecyAgentSimulationMode.KINEMATIC
  mesh=next(c for c in a.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name()=='PhysicalMesh')
  center=(mesh.get_socket_location('foot_l')+mesh.get_socket_location('foot_r'))*.5
  tested=[]
  for row in data['families']:
   target=center+V(3000,4000,2345)
   effective,difference,wanted,margin=call('GetValidAttackTarget',a,row['attack'],target)
   assert margin==0.,margin
   radius=math.hypot(effective.x-center.x,effective.y-center.y)
   assert abs(radius-row['radius_cm']-50)<1.e-5,(row['attack'],radius)
   assert effective.z==target.z and (wanted-target).length()<1.e-8
   assert (effective-wanted-difference).length()<1.e-8
   inside=center+V(1,2,-1000)
   result=call('GetValidAttackTarget',a,row['attack'],inside)
   assert (result[0]-inside).length()<1.e-8
   assert abs(result[3]-(radius-math.sqrt(5)))<1.e-5,result
   tested.append(dict(attack=row['attack'],radius_cm=radius))
  target=center+V(3000,4000,2345)
  baseline_b=call('GetValidAttackTarget',b,'jabL',target)[0]
  assert call('SetAttackTargetExtraReach',a,*([0.]*16))
  effective=call('GetValidAttackTarget',a,'jabL',target)[0]
  assert abs(math.hypot(effective.x-center.x,effective.y-center.y)-data['families'][0]['radius_cm'])<1.e-5
  assert (call('GetValidAttackTarget',b,'jabL',target)[0]-baseline_b).length()<1.e-8
  values=[float(i*7) for i in range(16)]
  assert call('SetAttackTargetExtraReach',a,*values)
  def check_profile():
   for row in data['families']:
    extra=values[order.index(row['attack'])]
    result=call('GetValidAttackTarget',a,row['attack'],target)
    radius=math.hypot(result[0].x-center.x,result[0].y-center.y)
    assert abs(radius-row['radius_cm']-extra)<1.e-5,(row['attack'],radius,extra)
    inside=center+V(1,2,-1000)
    assert abs(call('GetValidAttackTarget',a,row['attack'],inside)[3]-(radius-math.sqrt(5)))<1.e-5
   assert (call('GetValidAttackTarget',b,'jabL',target)[0]-baseline_b).length()<1.e-8
  check_profile()
  for bad in (-1.,float('nan'),float('inf')):
   invalid=values.copy();invalid[-1]=bad
   assert not call('SetAttackTargetExtraReach',a,*invalid)
   check_profile()
  assert call('SetAttackTargetExtraReach',a,*([50.]*16))
  for row in data['families']:
   p=call('GetValidAttackTarget',a,row['attack'],target)[0]
   assert abs(math.hypot(p.x-center.x,p.y-center.y)-row['radius_cm']-50)<1.e-5
  unknown=call('GetValidAttackTarget',a,'bad_attack',target)[0]
  assert math.hypot(unknown.x-center.x,unknown.y-center.y)<1.e-8 and unknown.z==target.z
  finish(dict(error='',families=tested,per_attack_profile=dict(zip(order,values)),independent_override=True,invalid_values_rejected_atomically=True,default_restored=True))
 except Exception:finish(dict(error=traceback.format_exc()))
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
