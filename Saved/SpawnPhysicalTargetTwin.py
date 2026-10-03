import unreal

world = unreal.EditorLevelLibrary.get_game_world()
physical = [
    actor for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
    if actor.get_simulation_mode() == unreal.ProphecyAgentSimulationMode.PHYSICAL
][0]
source_anim = physical.get_agent_mesh().get_anim_instance()
agent_id = source_anim.get_editor_property("agent_id")

for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent):
    if actor.actor_has_tag("PhysicalTargetTwin"):
        actor.destroy_actor()

transform = physical.get_actor_transform()
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
twin = subsystem.duplicate_actor(physical, world, unreal.Vector(0.0, 0.0, 0.0))
if twin is None:
    raise RuntimeError("PIE actor duplication failed")
twin.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
twin.set_actor_transform(transform, False, True)
twin.tags = [unreal.Name("PhysicalTargetTwin")]
twin.set_actor_enable_collision(False)
twin.get_agent_mesh().set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
twin_anim = twin.get_agent_mesh().get_anim_instance()
twin_anim.set_editor_property("agent_id", agent_id)
print("TWIN=" + twin.get_name() + " AGENT_ID=" + str(agent_id))
