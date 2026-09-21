import unreal
lib=unreal.ConstraintInstanceBlueprintLibrary
print([n for n in dir(lib) if n.startswith('get_')])
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if world:
    for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.ProphecyAgent):
        mesh=a.get_pose_reference_mesh()
        print(a.get_name(),[(i,str(lib.get_attached_body_names(c))) for i,c in enumerate(mesh.get_constraints(True))])
