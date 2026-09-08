"""Shared Blender -> Unreal FBX export settings.

Follows the established pipeline documented by:
- MetahumanToManny (Y Forward, Z Up, Face smoothing, no leaf bones)
- Blender-For-UnrealEngine / Epic forum consensus for skeletal meshes:
  work in centimeter scene units (scale_length=0.01) and export with
  apply_scale_options='FBX_SCALE_UNITS' (FBX Units Scale). Do NOT apply
  object transforms at export time for skeletal meshes.
"""

import bpy


def ensure_cm_scene():
    """Make 1 Blender unit == 1 cm (UE native)."""
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 0.01


def export_skeletal_fbx(filepath, armature, meshes):
    """Export armature + meshes with the standard UE skeletal settings."""
    ensure_cm_scene()
    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    for mesh in meshes:
        mesh.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.export_scene.fbx(
        filepath=filepath,
        use_selection=True,
        object_types={"ARMATURE", "MESH"},
        primary_bone_axis="Y",
        secondary_bone_axis="X",
        axis_forward="Y",
        axis_up="Z",
        apply_scale_options="FBX_SCALE_UNITS",
        apply_unit_scale=True,
        bake_anim=False,
        add_leaf_bones=False,
        mesh_smooth_type="FACE",
        use_tspace=True,
    )
