"""Render the native-rest Boss under exported UEFN animation skeletons."""

import json
import os
from pathlib import Path

import bpy
from mathutils import Vector


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
EXCHANGE = PROJECT / "Saved" / "BlenderExchange"
BLEND = Path(
    os.environ.get(
        "BOSS_ANIMATION_AUDIT_BLEND",
        str(EXCHANGE / "BossUEFN" / "Boss_UEFN_ExportClean.blend"),
    )
)
AUDIT_TAG = os.environ.get("BOSS_ANIMATION_AUDIT_TAG", "Current")
OUT_DIR = (
    PROJECT / "Saved" / "BlenderShots" / "BossUEFN" / AUDIT_TAG
)
AUDIT = (
    EXCHANGE
    / "BossUEFN"
    / f"Boss_UEFN_BlenderAnimationAudit_{AUDIT_TAG}.json"
)
FPS = 30

POSES = (
    ("Idle", EXCHANGE / "Anim_Idle.fbx", 1.0),
    ("Sprint", EXCHANGE / "Anim_Sprint.fbx", 0.28),
    ("Climb", EXCHANGE / "Anim_Climb.fbx", 2.0),
    ("CliffCatch", EXCHANGE / "Anim_CliffCatch.fbx", 0.8),
)


def evaluated_world_positions(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        return [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
    finally:
        evaluated.to_mesh_clear()


def bounds(points):
    minimum = [min(point[axis] for point in points) for axis in range(3)]
    maximum = [max(point[axis] for point in points) for axis in range(3)]
    return {
        "minimum": minimum,
        "maximum": maximum,
        "dimensions": [maximum[i] - minimum[i] for i in range(3)],
    }


def look_at(camera, target):
    camera.rotation_euler = (
        Vector(target) - camera.location
    ).to_track_quat("-Z", "Y").to_euler()


def import_animation(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(
        filepath=str(path),
        use_manual_orientation=False,
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
    imported = list(set(bpy.data.objects) - before)
    rigs = [obj for obj in imported if obj.type == "ARMATURE"]
    if len(rigs) != 1:
        raise RuntimeError(f"{path.name}: expected one animation armature")
    return rigs[0], imported


def main():
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 720
    scene.render.resolution_y = 960
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studio_light = "paint.sl"
    scene.display.shading.color_type = "SINGLE"
    scene.display.shading.single_color = (0.56, 0.61, 0.68)
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.world.color = (0.035, 0.035, 0.035)
    scene.render.fps = FPS

    source_rig = next(obj for obj in bpy.data.objects if obj.type == "ARMATURE")
    mesh = next(obj for obj in bpy.data.objects if obj.type == "MESH")
    source_names = [bone.name for bone in source_rig.data.bones]
    mesh_relative = source_rig.matrix_world.inverted_safe() @ mesh.matrix_world
    modifier = next(mod for mod in mesh.modifiers if mod.type == "ARMATURE")
    source_rig.hide_render = True

    camera_data = bpy.data.cameras.new("BossUEFNAuditCamera")
    camera_data.type = "ORTHO"
    camera = bpy.data.objects.new("BossUEFNAuditCamera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera

    report = {"blend": str(BLEND), "poses": {}}
    scene.frame_set(0)
    bpy.context.view_layer.update()
    neutral_points = evaluated_world_positions(mesh)
    neutral_box = bounds(neutral_points)
    neutral_center = Vector(
        tuple(
            (neutral_box["minimum"][axis] + neutral_box["maximum"][axis]) * 0.5
            for axis in range(3)
        )
    )
    neutral_height = neutral_box["dimensions"][2]
    neutral_images = {}
    for view, offset in (
        ("Front", Vector((0.0, -max(neutral_height * 2.5, 4.0), 0.0))),
        ("Side", Vector((max(neutral_height * 2.5, 4.0), 0.0, 0.0))),
    ):
        camera_data.ortho_scale = max(neutral_height * 1.15, 0.5)
        camera.location = neutral_center + offset
        look_at(camera, neutral_center)
        output = OUT_DIR / f"Blender_Boss_Neutral_{view}.png"
        scene.render.filepath = str(output)
        bpy.ops.render.render(write_still=True)
        neutral_images[view] = str(output)
    neck_center = Vector(
        (
            neutral_center.x,
            neutral_center.y,
            neutral_box["maximum"][2] - neutral_height * 0.16,
        )
    )
    camera_data.ortho_scale = neutral_height * 0.38
    camera.location = neck_center + Vector(
        (0.0, -max(neutral_height * 2.5, 4.0), 0.0)
    )
    look_at(camera, neck_center)
    neutral_neck = OUT_DIR / "Blender_Boss_Neutral_Neck.png"
    scene.render.filepath = str(neutral_neck)
    bpy.ops.render.render(write_still=True)
    neutral_images["Neck"] = str(neutral_neck)
    report["poses"]["Neutral"] = {
        "frame": 0,
        "bounds": neutral_box,
        "images": neutral_images,
    }

    for label, path, seconds in POSES:
        if not path.is_file():
            raise RuntimeError(f"Missing UEFN animation FBX: {path}")
        anim_rig, imported = import_animation(path)
        anim_names = [bone.name for bone in anim_rig.data.bones]
        if anim_names != source_names:
            raise RuntimeError(f"{label}: animation skeleton differs from Boss")
        for obj in imported:
            obj.hide_render = True
        modifier.object = anim_rig

        frame = int(round(seconds * FPS))
        scene.frame_set(frame)
        mesh.matrix_world = anim_rig.matrix_world @ mesh_relative
        bpy.context.view_layer.update()
        points = evaluated_world_positions(mesh)
        box = bounds(points)
        center = Vector(
            tuple(
                (box["minimum"][axis] + box["maximum"][axis]) * 0.5
                for axis in range(3)
            )
        )
        height = box["dimensions"][2]
        camera_data.ortho_scale = max(height * 1.15, 0.5)

        images = {}
        for view, offset in (
            ("Front", Vector((0.0, -max(height * 2.5, 4.0), 0.0))),
            ("Side", Vector((max(height * 2.5, 4.0), 0.0, 0.0))),
        ):
            camera.location = center + offset
            look_at(camera, center)
            output = OUT_DIR / f"Blender_Boss_{label}_{view}.png"
            scene.render.filepath = str(output)
            bpy.ops.render.render(write_still=True)
            images[view] = str(output)

        report["poses"][label] = {
            "animation_fbx": str(path),
            "sample_seconds": seconds,
            "frame": frame,
            "bounds": box,
            "images": images,
        }
        modifier.object = source_rig
        for obj in imported:
            bpy.data.objects.remove(obj, do_unlink=True)

    AUDIT.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print("BOSS_UEFN_BLENDER_ANIMATION_AUDIT=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
