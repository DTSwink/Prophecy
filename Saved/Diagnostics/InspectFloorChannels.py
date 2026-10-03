import unreal
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor):
 for c in a.get_components_by_class(unreal.PrimitiveComponent):
  p=c.get_world_location()
  if abs(p.z)<100 and c.get_collision_enabled()!=unreal.CollisionEnabled.NO_COLLISION:
   print(a.get_name(),c.get_name(),str(c.get_collision_object_type()),str(p))
