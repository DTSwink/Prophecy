"""Reimport body with update_skeleton_reference_pose=True for testing."""

import os
import unreal

EXCHANGE = os.path.join(unreal.Paths.project_dir(), "Saved", "BlenderExchange")
UEFN_SKELETON = "/Game/_mygame/SK_UEFN_Mannequin.SK_UEFN_Mannequin"
fbx_path = os.path.join(EXCHANGE, "Body_UEFN78.fbx")
destination = "/Game/_mygame/MetaHumans"
asset_name = "SKM_test_UEFN78_Body_RefPose"

full = destination + "/" + asset_name
if unreal.EditorAssetLibrary.does_asset_exist(full):
    unreal.EditorAssetLibrary.delete_asset(full)

skeleton = unreal.load_asset(UEFN_SKELETON)
options = unreal.FbxImportUI()
options.set_editor_property("import_mesh", True)
options.set_editor_property("import_as_skeletal", True)
options.set_editor_property("import_animations", False)
options.set_editor_property("import_materials", False)
options.set_editor_property("import_textures", False)
options.set_editor_property("create_physics_asset", False)
options.set_editor_property("skeleton", skeleton)
options.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
sm_data = options.get_editor_property("skeletal_mesh_import_data")
sm_data.set_editor_property("import_morph_targets", False)
sm_data.set_editor_property("update_skeleton_reference_pose", True)
sm_data.set_editor_property("use_t0_as_ref_pose", True)
sm_data.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)

task = unreal.AssetImportTask()
task.set_editor_property("filename", fbx_path)
task.set_editor_property("destination_path", destination)
task.set_editor_property("destination_name", asset_name)
task.set_editor_property("automated", True)
task.set_editor_property("save", True)
task.set_editor_property("replace_existing", True)
task.set_editor_property("options", options)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
print("IMPORTED|{}".format(list(task.get_editor_property("imported_object_paths"))))
print("REFPOSE_IMPORT_DONE")
