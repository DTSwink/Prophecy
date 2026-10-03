import unreal
world = unreal.EditorLevelLibrary.get_game_world()
for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent):
    if actor.get_simulation_mode() == unreal.ProphecyAgentSimulationMode.PHYSICAL:
        mesh = actor.get_agent_mesh()
        print('PHYSICAL_VALID constraints=%d collision=%s awake=%s' % (len(mesh.get_constraints(False)), mesh.get_collision_enabled(), mesh.is_any_rigid_body_awake()))
