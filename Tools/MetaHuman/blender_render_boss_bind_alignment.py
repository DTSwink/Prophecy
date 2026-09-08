"""Render the fitted-bind Boss mesh with hand/finger joint markers."""

from pathlib import Path

import bpy
from mathutils import Vector


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
BLEND = (
    PROJECT
    / "Saved"
    / "BlenderExchange"
    / "BossUEFN"
    / "Boss_UEFN_ExportClean.blend"
)
OUT_DIR = PROJECT / "Saved" / "BlenderShots" / "BossUEFNBindAlignment"


def look_at(camera, target):
    camera.rotation_euler = (
        target - camera.location
    ).to_track_quat("-Z", "Y").to_euler()


bpy.ops.wm.open_mainfile(filepath=str(BLEND))
OUT_DIR.mkdir(parents=True, exist_ok=True)
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.render.resolution_x = 1200
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.display.shading.light = "STUDIO"
scene.display.shading.studio_light = "paint.sl"
scene.display.shading.color_type = "OBJECT"
scene.display.shading.show_shadows = True
scene.display.shading.show_cavity = True
scene.world.color = (0.025, 0.025, 0.025)

rig = bpy.data.objects["root"]
mesh = bpy.data.objects["SKM_Boss_UEFN"]
mesh.color = (0.08, 0.10, 0.12, 1.0)
rig.hide_render = True

points = [mesh.matrix_world @ vertex.co for vertex in mesh.data.vertices]
minimum = Vector(tuple(min(point[i] for point in points) for i in range(3)))
maximum = Vector(tuple(max(point[i] for point in points) for i in range(3)))
height = maximum.z - minimum.z

hand_bones = [
    bone
    for bone in rig.data.bones
    if bone.name.startswith(
        (
            "hand_",
            "thumb_",
            "index_",
            "middle_",
            "ring_",
            "pinky_",
        )
    )
]
for bone in hand_bones:
    for suffix, local_position in (
        ("Head", bone.head_local),
        ("Tail", bone.tail_local),
    ):
        position = rig.matrix_world @ local_position
        bpy.ops.mesh.primitive_ico_sphere_add(
            subdivisions=2,
            radius=height * 0.004,
            location=position,
        )
        marker = bpy.context.object
        marker.name = f"JOINT_{bone.name}_{suffix}"
        marker.color = (
            (1.0, 0.12, 0.02, 1.0)
            if suffix == "Head"
            else (1.0, 0.65, 0.02, 1.0)
        )

camera_data = bpy.data.cameras.new("BindAlignmentCamera")
camera_data.type = "ORTHO"
camera = bpy.data.objects.new("BindAlignmentCamera", camera_data)
scene.collection.objects.link(camera)
scene.camera = camera

center = (minimum + maximum) * 0.5
camera_data.ortho_scale = height * 1.12
camera.location = center + Vector((0.0, -height * 2.5, 0.0))
look_at(camera, center)
scene.render.filepath = str(OUT_DIR / "Boss_FittedBind_Front.png")
bpy.ops.render.render(write_still=True)

for side, hand_name in (("Left", "hand_l"), ("Right", "hand_r")):
    hand = rig.data.bones[hand_name]
    target = rig.matrix_world @ hand.head_local
    camera_data.ortho_scale = height * 0.22
    camera.location = target + Vector((0.0, -height * 2.5, 0.0))
    look_at(camera, target)
    scene.render.filepath = str(
        OUT_DIR / f"Boss_FittedBind_{side}Hand.png"
    )
    bpy.ops.render.render(write_still=True)

print("BOSS_BIND_ALIGNMENT_RENDERS=" + str(OUT_DIR))
