import os

import unreal

EXCHANGE = os.path.join(unreal.Paths.project_dir(), "Saved", "BlenderExchange")
UEFN_SKELETON = "/Game/_mygame/SK_UEFN_Mannequin.SK_UEFN_Mannequin"

IMPORTS = [
    (os.path.join(EXCHANGE, "Body_UEFN78.fbx"), "/Game/_mygame/MetaHumans", "SKM_test_UEFN78_Body"),
    (os.path.join(EXCHANGE, "Face_UEFN.fbx"), "/Game/_mygame/MetaHumans", "SKM_test_UEFN78_Face"),
]

skeleton = unreal.load_asset(UEFN_SKELETON)
if skeleton is None:
    raise RuntimeError("UEFN skeleton missing")
bone_count_before = len(unreal.SkeletonEditorLibrary.get_bone_names(skeleton)) if hasattr(unreal, "SkeletonEditorLibrary") else -1

for fbx_path, destination, asset_name in IMPORTS:
    if not os.path.isfile(fbx_path):
        raise RuntimeError("Missing FBX " + fbx_path)
    full = destination + "/" + asset_name
    if unreal.EditorAssetLibrary.does_asset_exist(full):
        unreal.EditorAssetLibrary.delete_asset(full)

    options = unreal.FbxImportUI()
    options.set_editor_property("import_mesh", True)
    options.set_editor_property("import_as_skeletal", True)
    options.set_editor_property("import_animations", False)
    options.set_editor_property("import_materials", False)
    options.set_editor_property("import_textures", False)
    options.set_editor_property("create_physics_asset", False)
    options.set_editor_property("skeleton", skeleton)
    options.set_editor_property(
        "mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH
    )
    sm_data = options.get_editor_property("skeletal_mesh_import_data")
    sm_data.set_editor_property("import_morph_targets", False)
    sm_data.set_editor_property("update_skeleton_reference_pose", False)
    sm_data.set_editor_property("use_t0_as_ref_pose", False)
    sm_data.set_editor_property(
        "normal_import_method",
        unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS,
    )

    task = unreal.AssetImportTask()
    task.set_editor_property("filename", fbx_path)
    task.set_editor_property("destination_path", destination)
    task.set_editor_property("destination_name", asset_name)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("options", options)

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    imported = list(task.get_editor_property("imported_object_paths"))
    print("IMPORT|{}|{}".format(asset_name, imported))
    if not imported:
        raise RuntimeError("Import produced nothing for " + asset_name)

    mesh = unreal.load_asset(full)
    mesh_skeleton = mesh.get_editor_property("skeleton")
    print("IMPORT_SKELETON|{}|{}".format(asset_name, mesh_skeleton.get_path_name()))
    if mesh_skeleton.get_path_name() != UEFN_SKELETON:
        raise RuntimeError("Mesh bound to wrong skeleton!")

print("IMPORT_REDUCED_DONE")
