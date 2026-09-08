"""Print structural summaries for the fitted body, face, and Sequencer pose FBXs."""

import json
from pathlib import Path

import bpy


ROOT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
EXCHANGE = ROOT / "Saved" / "BlenderExchange"
SOURCES = (
    EXCHANGE / "Body_MH342.fbx",
    EXCHANGE / "Face_MH.fbx",
    EXCHANGE / "MetaHuman_SequencerModifiedPose_BakedAnim.fbx",
)


def import_fbx(path):
    before = set(bpy.data.objects)
    before_actions = set(bpy.data.actions)
    bpy.ops.import_scene.fbx(
        filepath=str(path),
        global_scale=1.0,
        bake_space_transform=False,
        use_custom_normals=True,
        use_anim=True,
        ignore_leaf_bones=False,
        force_connect_children=False,
        automatic_bone_orientation=False,
        primary_bone_axis="Y",
        secondary_bone_axis="X",
        use_prepost_rot=True,
        axis_forward="-Z",
        axis_up="Y",
    )
    return (
        list(set(bpy.data.objects) - before),
        list(set(bpy.data.actions) - before_actions),
    )


bpy.ops.wm.read_factory_settings(use_empty=True)
result = []
for source in SOURCES:
    objects, actions = import_fbx(source)
    entry = {"source": str(source), "objects": []}
    for obj in objects:
        item = {
            "name": obj.name,
            "type": obj.type,
            "parent": obj.parent.name if obj.parent else None,
            "scale": list(obj.scale),
            "world_scale": list(obj.matrix_world.to_scale()),
        }
        if obj.type == "ARMATURE":
            item.update({
                "bone_count": len(obj.data.bones),
                "root_bones": [b.name for b in obj.data.bones if b.parent is None],
                "sample_bones": [b.name for b in list(obj.data.bones)[:25]],
                "action": obj.animation_data.action.name
                if obj.animation_data and obj.animation_data.action else None,
            })
        elif obj.type == "MESH":
            item.update({
                "vertex_count": len(obj.data.vertices),
                "polygon_count": len(obj.data.polygons),
                "vertex_groups": len(obj.vertex_groups),
                "armature_modifiers": [
                    m.object.name if m.object else None
                    for m in obj.modifiers if m.type == "ARMATURE"
                ],
            })
        entry["objects"].append(item)
    entry["actions"] = [
        {"name": action.name, "frame_range": list(action.frame_range)}
        for action in actions
    ]
    result.append(entry)

print("SOURCE_INSPECTION=" + json.dumps(result, sort_keys=True))
