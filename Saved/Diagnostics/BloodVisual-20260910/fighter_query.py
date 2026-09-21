import unreal,builtins,json
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world();a=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)[0];c=next(c for c in a.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name()=='PhysicalMesh')
print('QUERY_PROFILE',c.get_collision_profile_name(),c.get_collision_object_type(),c.get_editor_property('body_instance').get_editor_property('collision_responses'))
for name in dir(unreal.CollisionChannel):
 if name.startswith('ECC_'):
  ch=getattr(unreal.CollisionChannel,name);print('RESPONSE',ch,c.get_collision_response_to_channel(ch))
g=unreal.get_default_object(unreal.GameplayStatics);p=c.get_socket_location('head')
print('TRACE_ENUM',[n for n in dir(unreal.TraceTypeQuery) if n.isupper()])
for i in range(1,8):
 ch=getattr(unreal.TraceTypeQuery,'TRACE_TYPE_QUERY'+str(i),None)
 if ch is None:continue
 for direction in [unreal.Vector(1,0,0),unreal.Vector(0,1,0),unreal.Vector(0,0,1)]:
  h=unreal.SystemLibrary.line_trace_single(w,p+direction*120,p-direction*120,ch,True,[],unreal.DrawDebugTrace.NONE,True)
  if h:print('TRACE',i,str(direction),g.call_method('BreakHitResult',args=(h,))[9:16])
print('COMPONENT',c.call_method('K2_LineTraceComponent',args=(p+unreal.Vector(0,0,100),p-unreal.Vector(0,0,100),True,False,False)))
