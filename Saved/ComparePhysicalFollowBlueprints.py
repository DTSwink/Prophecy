import json
import unreal


ASSETS = {
    "pose": "/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent",
    "cmc": "/Game/_mygame/SandboxCharacter_CMC",
}


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
        "socket": str(safe(lambda: component.get_attach_socket_name(), "")),
        "active": safe(lambda: component.is_active()),
        "tick_enabled": safe(lambda: component.is_component_tick_enabled()),
    }
    for name in [
        "relative_location", "relative_rotation", "relative_scale3d", "mobility",
        "auto_activate", "component_tags", "primary_component_tick",
        "skeletal_mesh_asset", "physics_asset_override", "animation_mode", "anim_class",
        "enable_update_rate_optimizations", "visibility_based_anim_tick_option",
        "component_use_fixed_skel_bounds", "update_joints_from_animation", "blend_physics",
        "disable_post_process_blueprint", "physics_transform_update_mode",
        "kinematic_bones_update_type", "defer_kinematic_bone_update",
        "leader_pose_component", "enable_gravity", "body_instance",
    ]:
        value = prop(component, name)
        if value != "<unavailable>":
            info[name] = value
    info["collision_profile"] = str(safe(lambda: component.get_collision_profile_name(), "<unavailable>"))
    info["collision_enabled"] = str(safe(lambda: component.get_collision_enabled(), "<unavailable>"))
    info["simulating"] = safe(lambda: component.is_simulating_physics())
    return info


def node_info(node):
    item = {
        "name": node.get_name(),
        "class": node.get_class().get_name(),
        "title": str(safe(lambda: node.get_node_title(unreal.NodeTitleType.FULL_TITLE), "")),
    }
    for name in [
        "function_reference", "variable_reference", "event_reference",
        "custom_function_name", "delegate_reference", "node_comment",
    ]:
        value = prop(node, name)
        if value != "<unavailable>":
            item[name] = value
    pins = safe(lambda: node.get_editor_property("pins"), []) or []
    item["pins"] = []
    for pin in pins:
        pin_name = str(safe(lambda: pin.get_editor_property("pin_name"), ""))
        linked = safe(lambda: pin.get_editor_property("linked_to"), []) or []
        item["pins"].append({
            "name": pin_name,
            "direction": str(safe(lambda: pin.get_editor_property("direction"), "")),
            "default": str(safe(lambda: pin.get_editor_property("default_value"), "")),
            "linked": [str(x) for x in linked],
        })
    return item


def inspect_asset(path):
    blueprint = unreal.EditorAssetLibrary.load_asset(path)
    generated_class = unreal.EditorAssetLibrary.load_blueprint_class(path)
    if not blueprint or not generated_class:
        return {"error": "asset or generated class missing", "path": path}
    defaults = unreal.get_default_object(generated_class)
    components = defaults.get_components_by_class(unreal.ActorComponent)
    graph = safe(lambda: unreal.BlueprintEditorLibrary.find_event_graph(blueprint))
    nodes = []
    if graph:
        objects = safe(lambda: unreal.get_objects_with_outer(graph, include_nested_objects=True), []) or []
        nodes = [node_info(obj) for obj in objects if obj.get_class().get_name().startswith("K2Node")]
    return {
        "path": path,
        "parent_class": str(safe(lambda: blueprint.parent_class, "")),
        "generated_class": str(generated_class),
        "actor_tick": prop(defaults, "primary_actor_tick"),
        "components": [component_info(c) for c in components],
        "nodes": nodes,
    }


result = {name: inspect_asset(path) for name, path in ASSETS.items()}
print("PHYSICAL_BP_COMPARE_BEGIN")
print(json.dumps(result, indent=2, default=str))
print("PHYSICAL_BP_COMPARE_END")
