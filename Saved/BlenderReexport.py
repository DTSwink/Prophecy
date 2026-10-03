"""Re-export Body_UEFN78 and Face_UEFN so UE imports at true centimeter size.

UE-exported FBX files carry raw centimeter values with UnitScaleFactor 1.0.
Blender's meter-based exports kept getting multiplied by 100 on UE import, so
replicate the UE layout exactly: bake object transforms so raw data values are
centimeter numbers, declare the scene unit as centimeters, and export with
FBX_SCALE_NONE so no unit conversion happens.
"""

import os
import sys

import bpy

EXCHANGE = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\BlenderExchange"

JOBS = [
    ("Body_UEFN78.blend", "Body_UEFN78.fbx"),
    ("Face_UEFN.blend", "Face_UEFN.fbx"),
]

for blend_name, fbx_name in JOBS:
    bpy.ops.wm.open_mainfile(filepath=os.path.join(EXCHANGE, blend_name))
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]

    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    for m in meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = arm
    # Blend files hold UE-imported objects at 0.01 scale whose raw data is
    # 100x the centimeter numbers (Blender's FBX importer bakes the cm->m
    # conversion into the data and compensates with object scale). One
    # transform_apply turns raw values into true centimeter numbers.
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Declare 1 Blender unit = 1 cm so the exporter does no unit conversion.
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 0.01

    pelvis = arm.data.bones.get("pelvis")
    print("PREEXPORT|{}|pelvis_raw_z={:.3f}|arm_scale={}".format(
        blend_name, pelvis.head_local.z if pelvis else -1.0, tuple(arm.scale)))

    out = os.path.join(EXCHANGE, fbx_name)
    bpy.ops.export_scene.fbx(
        filepath=out,
        use_selection=True,
        object_types={"ARMATURE", "MESH"},
        add_leaf_bones=False,
        apply_scale_options="FBX_SCALE_NONE",
        apply_unit_scale=True,
        global_scale=1.0,
        mesh_smooth_type="FACE",
        use_tspace=False,
        bake_anim=False,
    )
    print("REEXPORT|{}|bytes={}".format(out, os.path.getsize(out)))

print("REEXPORT_DONE")
sys.stdout.flush()
