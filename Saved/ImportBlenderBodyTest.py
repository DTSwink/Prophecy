"""Import the Blender-reduced body onto the untouched UEFN Skeleton."""

import os

import unreal


EXCHANGE = os.path.join(unreal.Paths.project_dir(), "Saved", "BlenderExchange")
FBX = os.path.join(EXCHANGE, "Body_UEFN78.fbx")
SKELETON_PATH = "/Game/_mygame/SK_UEFN_Mannequin.SK_UEFN_Mannequin"
ASSET_PATH = "/Game/_mygame/MetaHumans/SKM_test_UEFNBlenderBodyTest"


if not os.path.isfile(FBX):
    raise RuntimeError("Missing Blender FBX: " + FBX)
skeleton = unreal.load_asset(SKELETON_PATH)
if skeleton is None:
    raise RuntimeError("Missing UEFN Skeleton: " + SKELETON_PATH)
if unreal.EditorAssetLibrary.does_asset_exist(ASSET_PATH):
    unreal.EditorAssetLibrary.delete_asset(ASSET_PATH)

options = unreal.FbxImportUI()
options.set_editor_property("import_mesh", True)
options.set_editor_property("import_as_skeletal", True)
options.set_editor_property("import_animations", False)
options.set_editor_property("import_materials", False)
options.set_editor_property("import_textures", False)
options.set_editor_property("create_physics_asset", False)
options.set_editor_property("skeleton", skeleton)
options.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
mesh_options = options.get_editor_property("skeletal_mesh_import_data")
mesh_options.set_editor_property("import_morph_targets", False)
mesh_options.set_editor_property("update_skeleton_reference_pose", False)
mesh_options.set_editor_property("use_t0_as_ref_pose", False)
mesh_options.set_editor_property(
    "normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
)

task = unreal.AssetImportTask()
task.set_editor_property("filename", FBX)
task.set_editor_property("destination_path", "/Game/_mygame/MetaHumans")
task.set_editor_property("destination_name", "SKM_test_UEFNBlenderBodyTest")
task.set_editor_property("automated", True)
task.set_editor_property("save", True)
task.set_editor_property("replace_existing", True)
task.set_editor_property("options", options)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

imported = list(task.get_editor_property("imported_object_paths"))
if not imported:
    raise RuntimeError("Blender FBX import produced no asset")
mesh = unreal.load_asset(ASSET_PATH)
if not isinstance(mesh, unreal.SkeletalMesh):
    raise RuntimeError("Imported object is not a SkeletalMesh")
mesh_skeleton = mesh.get_editor_property("skeleton")
if mesh_skeleton.get_path_name() != SKELETON_PATH:
    raise RuntimeError("Imported body is not using the untouched UEFN Skeleton")

skeleton_modifier = unreal.SkeletonModifier()
if not skeleton_modifier.set_skeletal_mesh(mesh):
    raise RuntimeError("Could not inspect imported skeleton")
bone_names = [str(name) for name in skeleton_modifier.get_all_bone_names()]
skin_modifier = unreal.SkinWeightModifier()
if not skin_modifier.set_skeletal_mesh(mesh):
    raise RuntimeError("Could not inspect imported weights")
bounds = mesh.get_bounds()
print("BLENDER_IMPORT|{}".format(imported))
print("BLENDER_IMPORT_SKELETON|{}".format(mesh_skeleton.get_path_name()))
print("BLENDER_IMPORT_BONES|{}".format(len(bone_names)))
print("BLENDER_IMPORT_VERTICES|{}".format(skin_modifier.get_num_vertices()))
print(
    "BLENDER_IMPORT_BOUNDS|origin=({:.3f},{:.3f},{:.3f})|extent=({:.3f},{:.3f},{:.3f})".format(
        bounds.origin.x,
        bounds.origin.y,
        bounds.origin.z,
        bounds.box_extent.x,
        bounds.box_extent.y,
        bounds.box_extent.z,
    )
)
print("BLENDER_IMPORT_DONE")
