import unreal,builtins
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() or unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world();a=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)[0];mesh=a.get_components_by_class(unreal.SkeletalMeshComponent)[0]
print('COMP_DELEGATE',type(mesh.on_component_hit).__doc__)
print('ACTOR_DELEGATE',type(a.on_actor_hit).__doc__)
class Receiver:
 def __call__(self,*args):print('TEST_CALLBACK',len(args))
r=Receiver();d=mesh.on_component_hit
try:
 d.add_callable(r);print('BOUND_CALLABLE_OBJECT');d.remove_callable(r)
except Exception as e:print('BIND_ERROR',repr(e))
