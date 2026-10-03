import unreal

world = unreal.EditorLevelLibrary.get_game_world()
agents = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
mesh = agents[0].get_agent_mesh()
constraints = mesh.get_constraints(False)
print("CONSTRAINT_COUNT=" + str(len(constraints)))
if constraints:
    print("ACCESSOR_DIR=" + ",".join(name for name in dir(constraints[0]) if not name.startswith("__")))
    print("LIB_DIR=" + ",".join(name for name in dir(unreal.ConstraintInstanceBlueprintLibrary) if "bone" in name.lower() or "name" in name.lower() or "constraint" in name.lower()))
    print("ATTACHED_DOC=" + str(unreal.ConstraintInstanceBlueprintLibrary.get_attached_body_names.__doc__))
    for index, accessor in enumerate(constraints):
        print("ATTACHED_%d=" % index + str(unreal.ConstraintInstanceBlueprintLibrary.get_attached_body_names(accessor)))
print("MESH_API=" + ",".join(name for name in dir(mesh) if "physics_asset" in name.lower()))
