import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
a=next(a for a in unreal.GameplayStatics.get_all_actors_of_class(ed.get_editor_world(),unreal.Actor) if a.get_class().get_name()=='A_Pot_C')
c=a.get_component_by_class(unreal.PhysicsConstraintComponent)
lib=unreal.ConstraintInstanceBlueprintLibrary
print('LINEAR',lib.get_linear_limits(c.get_constraint()))
print('COLLISION',lib.get_disable_collsion(c.get_constraint()))
print('SOFT',lib.get_linear_soft_limit_params(c.get_constraint()))
print([n for n in dir(lib) if 'soft' in n or 'projection' in n])
