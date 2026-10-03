import json
import unreal

world = unreal.EditorLevelLibrary.get_game_world()
physical = [
    actor for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
    if actor.get_simulation_mode() == unreal.ProphecyAgentSimulationMode.PHYSICAL
][0]
twin = [
    actor for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
    if actor.actor_has_tag("PhysicalTargetTwin")
][0]
physical_mesh = physical.get_agent_mesh()
target_mesh = twin.get_agent_mesh()
bones = ("pelvis", "thigh_l", "calf_l", "foot_l", "thigh_r", "calf_r", "foot_r",
         "spine_05", "upperarm_l", "lowerarm_l", "upperarm_r", "lowerarm_r", "head")
out = {}
for bone in bones:
    actual = physical_mesh.get_socket_transform(bone, unreal.RelativeTransformSpace.RTS_WORLD)
    target = target_mesh.get_socket_transform(bone, unreal.RelativeTransformSpace.RTS_WORLD)
    location_error = unreal.MathLibrary.vector_distance(actual.translation, target.translation)
    delta = actual.rotation.inverse() * target.rotation
    angle = unreal.MathLibrary.radians_to_degrees(delta.get_angle())
    if angle > 180.0:
        angle = 360.0 - angle
    out[bone] = {"cm": round(location_error, 4), "deg": round(angle, 4)}
print("POSE_ERROR=" + json.dumps(out, separators=(",", ":")))
