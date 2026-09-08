"""Report skeletal-mesh assets used by the four requested level actors."""

import json
import unreal


TARGET_LABELS = {"BP_boss", "BP_Enemy", "BP_girl", "BP_savagee"}


def object_path(obj):
    return obj.get_path_name() if obj else None


def component_report(component):
    mesh = component.get_editor_property("skeletal_mesh_asset")
    location = component.get_editor_property("relative_location")
    rotation = component.get_editor_property("relative_rotation")
    scale = component.get_editor_property("relative_scale3d")
    return {
        "component_name": component.get_name(),
        "component_class": component.get_class().get_name(),
        "skeletal_mesh": object_path(mesh),
        "visible": bool(component.get_editor_property("visible")),
        "relative_location": [location.x, location.y, location.z],
        "relative_rotation": [rotation.roll, rotation.pitch, rotation.yaw],
        "relative_scale": [scale.x, scale.y, scale.z],
    }


subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
reports = []
for actor in subsystem.get_all_level_actors():
    label = actor.get_actor_label()
    if label not in TARGET_LABELS:
        continue
    components = actor.get_components_by_class(unreal.SkeletalMeshComponent)
    child_reports = []
    for child_component in actor.get_components_by_class(unreal.ChildActorComponent):
        child = child_component.get_child_actor()
        if child:
            child_reports.append(
                {
                    "label": child.get_actor_label(),
                    "path": child.get_path_name(),
                    "skeletal_components": [
                        component_report(component)
                        for component in child.get_components_by_class(unreal.SkeletalMeshComponent)
                    ],
                }
            )
    reports.append(
        {
            "label": label,
            "actor_path": actor.get_path_name(),
            "actor_class": actor.get_class().get_path_name(),
            "skeletal_components": [component_report(component) for component in components],
            "child_actors": child_reports,
        }
    )

print("FOUR_CHARACTER_MESH_REPORT=" + json.dumps(sorted(reports, key=lambda item: item["label"]), indent=2))
