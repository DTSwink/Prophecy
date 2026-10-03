import json
import math
import re
from pathlib import Path

import bpy


INPUT_DIR = Path(r"C:\Users\singerie\Documents\SmartsuitStudioProjects\kjb\MotionLibrary")
OUTPUT_DIR = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\RokokoCarrierRootedFixedFBX")


def sanitize_name(path):
    name = path.stem
    name = re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_")
    name = re.sub(r"_+", "_", name)
    return name or "RokokoAnimation"


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def find_armature():
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError("No armature imported from FBX.")
    return max(armatures, key=lambda obj: len(obj.data.bones))


def find_action(armature):
    if armature.animation_data and armature.animation_data.action:
        return armature.animation_data.action
    if bpy.data.actions:
        action = bpy.data.actions[0]
        armature.animation_data_create()
        armature.animation_data.action = action
        return action
    return None


def estimate_floor_to_hips_cm(armature):
    hips = armature.data.bones.get("Hips")
    if hips is None:
        raise RuntimeError("Expected Rokoko/Xsens Hips bone.")

    min_height = min(
        min(bone.head_local.y, bone.tail_local.y)
        for bone in armature.data.bones
    )
    return hips.head_local.y - min_height


def subtract_hips_height_from_animation(action, height_cm):
    if not action:
        return
    fcurves = []
    if hasattr(action, "fcurves"):
        fcurves.extend(action.fcurves)
    else:
        for layer in getattr(action, "layers", []):
            for strip in getattr(layer, "strips", []):
                for channelbag in getattr(strip, "channelbags", []):
                    fcurves.extend(channelbag.fcurves)

    hips_location_path = 'pose.bones["Hips"].location'
    for fcurve in fcurves:
        if fcurve.data_path == hips_location_path and fcurve.array_index == 1:
            for key in fcurve.keyframe_points:
                key.co.y -= height_cm
                key.handle_left.y -= height_cm
                key.handle_right.y -= height_cm
            fcurve.update()


def add_ground_root_and_raise_reference_pose(armature, height_cm):
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT")

    edit_bones = armature.data.edit_bones
    hips = edit_bones.get("Hips")
    if hips is None:
        bpy.ops.object.mode_set(mode="OBJECT")
        raise RuntimeError("Expected Rokoko/Xsens Hips bone.")

    for bone in edit_bones:
        if not (bone.parent and bone.use_connect):
            bone.head.y += height_cm
        bone.tail.y += height_cm

    root = edit_bones.new("Root")
    root.head = (0.0, 0.0, 0.0)
    root.tail = (0.0, max(5.0, height_cm * 0.08), 0.0)
    hips.parent = root
    hips.use_connect = False

    bpy.ops.object.mode_set(mode="OBJECT")


def make_carrier_mesh(armature):
    mesh = bpy.data.meshes.new("RokokoCarrierMeshData")
    obj = bpy.data.objects.new("RokokoCarrierMesh", mesh)
    bpy.context.collection.objects.link(obj)

    vertices = []
    faces = []
    weights = []
    size = 0.75
    offsets = [
        (size, 0.0, 0.0),
        (-size, 0.0, 0.0),
        (0.0, size, 0.0),
        (0.0, 0.0, size),
    ]

    for bone in armature.data.bones:
        if bone.name == "Root":
            continue
        center = bone.head_local.copy()
        if (bone.tail_local - bone.head_local).length > 0.001:
            center = bone.head_local.lerp(bone.tail_local, 0.35)

        start = len(vertices)
        for offset in offsets:
            vertices.append((center.x + offset[0], center.y + offset[1], center.z + offset[2]))
            weights.append(bone.name)

        faces.extend([
            (start + 0, start + 2, start + 3),
            (start + 2, start + 1, start + 3),
            (start + 1, start + 0, start + 3),
            (start + 0, start + 1, start + 2),
        ])

    mesh.from_pydata(vertices, [], faces)
    mesh.update()

    groups = {bone.name: obj.vertex_groups.new(name=bone.name) for bone in armature.data.bones}
    for index, bone_name in enumerate(weights):
        groups[bone_name].add([index], 1.0, "REPLACE")

    obj.parent = armature
    modifier = obj.modifiers.new("RokokoCarrierArmature", "ARMATURE")
    modifier.object = armature

    return obj


def export_carrier_fbx(source_path, destination_path):
    reset_scene()
    bpy.ops.import_scene.fbx(filepath=str(source_path), automatic_bone_orientation=False)

    armature = find_armature()
    action = find_action(armature)
    floor_to_hips_cm = estimate_floor_to_hips_cm(armature)
    add_ground_root_and_raise_reference_pose(armature, floor_to_hips_cm)
    subtract_hips_height_from_animation(action, floor_to_hips_cm)
    carrier = make_carrier_mesh(armature)

    if action:
        start, end = action.frame_range
        bpy.context.scene.frame_start = max(1, int(math.floor(start)))
        bpy.context.scene.frame_end = max(bpy.context.scene.frame_start, int(math.ceil(end)))

    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    carrier.select_set(True)
    bpy.context.view_layer.objects.active = armature

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.fbx(
        filepath=str(destination_path),
        use_selection=True,
        object_types={"ARMATURE", "MESH"},
        use_mesh_modifiers=True,
        add_leaf_bones=False,
        primary_bone_axis="Y",
        secondary_bone_axis="X",
        use_armature_deform_only=False,
        armature_nodetype="ROOT",
        bake_anim=True,
        bake_anim_use_all_bones=True,
        bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False,
        bake_anim_force_startend_keying=True,
        bake_anim_step=1.0,
        bake_anim_simplify_factor=0.0,
        path_mode="AUTO",
        axis_forward="-Z",
        axis_up="Y",
    )

    return {
        "source": str(source_path),
        "output": str(destination_path),
        "armature": armature.name,
        "bone_count": len(armature.data.bones),
        "floor_to_hips_cm": floor_to_hips_cm,
        "hips_reference_height_cm": armature.data.bones["Hips"].head_local.y,
        "action": action.name if action else None,
        "frame_start": bpy.context.scene.frame_start,
        "frame_end": bpy.context.scene.frame_end,
    }


def main():
    fbx_files = sorted(INPUT_DIR.glob("*.fbx"))
    if not fbx_files:
        raise RuntimeError(f"No FBX files found in {INPUT_DIR}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report = []
    for source_path in fbx_files:
        output_name = sanitize_name(source_path) + "_RootedCarrier.fbx"
        report.append(export_carrier_fbx(source_path, OUTPUT_DIR / output_name))

    print("ROKOKO_ROOTED_CARRIER_EXPORT_REPORT=" + json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
