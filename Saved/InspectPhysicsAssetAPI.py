import unreal

world = unreal.EditorLevelLibrary.get_game_world()
agent = [
    actor for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
    if actor.get_simulation_mode() == unreal.ProphecyAgentSimulationMode.PHYSICAL
][0]
component = agent.get_agent_mesh()
skeletal_mesh = component.get_skeletal_mesh_asset()
print("SKM=" + str(skeletal_mesh))
print("SKM_API=" + ",".join(name for name in dir(skeletal_mesh) if "physics" in name.lower() or "skeleton" in name.lower()))
for prop in ("physics_asset", "physics_asset_override"):
    try:
        print(prop + "=" + str(skeletal_mesh.get_editor_property(prop)))
    except Exception as exc:
        print(prop + "_ERR=" + str(exc))
asset = skeletal_mesh.get_editor_property("physics_asset")
print("PA_API=" + ",".join(name for name in dir(asset) if "constraint" in name.lower() or "body" in name.lower() or "setup" in name.lower()))
for prop in ("constraint_setup", "skeletal_body_setups", "body_setup"):
    try:
        value = asset.get_editor_property(prop)
        print(prop + "=" + str(value)[:2000])
    except Exception as exc:
        print(prop + "_ERR=" + str(exc))
