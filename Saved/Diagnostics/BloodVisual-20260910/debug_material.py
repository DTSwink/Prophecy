import unreal,builtins
s=builtins._blood_visual;m=s['fighter_manager'];w=m.get_world()
print('DEBUG_MASK',m.debug_show_mask_on_painted_materials)
for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
 for c in a.get_components_by_class(unreal.SkeletalMeshComponent):
  mid=c.get_material(0)
  if isinstance(mid,unreal.MaterialInstanceDynamic):print(c.get_path_name(),mid.get_scalar_parameter_value('DebugShowBloodMask'))
m.set_debug_show_mask_on_painted_materials(False)
print('MASK_DEBUG_DISABLED_FOR_CAPTURE')
