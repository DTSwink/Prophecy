import json
import unreal


def safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def prop(obj, name):
    value = safe(lambda: obj.get_editor_property(name), "<unavailable>")
    return str(value)


def component_info(component):
    parent = safe(lambda: component.get_attach_parent())
    info = {
        "name": component.get_name(),
        "class": component.get_class().get_name(),
        "parent": parent.get_name() if parent else None,
        "tick_enabled": safe(lambda: component.is_component_tick_enabled()),
        "active": safe(lambda: component.is_active()),
    }
    for name in [
        "relative_location", "relative_rotation", "relative_scale3d", "primary_component_tick",
        "skeletal_mesh_asset", "physics_asset_override", "animation_mode", "anim_class",
        "enable_update_rate_optimizations", "visibility_based_anim_tick_option",
        "update_joints_from_animation", "blend_physics", "physics_transform_update_mode",
        "kinematic_bones_update_type", "defer_kinematic_bone_update", "leader_pose_component",
        "enable_gravity", "body_instance",
    ]:
        value = prop(component, name)
        if value != "<unavailable>":
            info[name] = value
    if isinstance(component, unreal.SkeletalMeshComponent):
        info["world_location"] = str(component.get_world_location())
        info["world_rotation"] = str(component.get_world_rotation())
        info["collision_profile"] = str(safe(lambda: component.get_collision_profile_name(), ""))
        info["collision_enabled"] = str(safe(lambda: component.get_collision_enabled(), ""))
        info["simulating"] = safe(lambda: component.is_simulating_physics())
        for bone in ["pelvis", "thigh_l", "foot_l"]:
            info[bone + "_world"] = str(safe(lambda b=bone: component.get_socket_transform(b), ""))
    if isinstance(component, unreal.PhysicalAnimationComponent):
        info["dir_mesh"] = [n for n in dir(component) if "skeletal" in n.lower() or "mesh" in n.lower()]
        info["assigned_mesh"] = str(safe(lambda: component.get_skeletal_mesh(), "<unavailable>"))
    return info


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
selected = []
for actor in actors:
    class_name = actor.get_class().get_name()
    components = actor.get_components_by_class(unreal.ActorComponent)
    component_names = [c.get_name() for c in components]
    if ("BP_ProphecyManualPoseAgent" in class_name or
            "SandboxCharacter_CMC" in class_name or
            "PhysicalMesh" in component_names):
        selected.append({
            "name": actor.get_name(),
            "class": class_name,
            "actor_transform": str(actor.get_actor_transform()),
            "actor_tick": prop(actor, "primary_actor_tick"),
            "components": [component_info(c) for c in components],
        })

print("PHYSICAL_LIVE_COMPARE_BEGIN")
print(json.dumps(selected, indent=2))
print("PHYSICAL_LIVE_COMPARE_END")
