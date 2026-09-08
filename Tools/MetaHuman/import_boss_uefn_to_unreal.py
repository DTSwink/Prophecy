"""Import the clean Boss FBX onto the existing UEFN Skeleton asset."""

import json
import os

import unreal


PROJECT = unreal.Paths.project_dir()
FBX = os.path.join(
    PROJECT,
    "Saved",
    "BlenderExchange",
    "BossUEFN",
    "SKM_Boss_UEFN.fbx",
)
DESTINATION = "/Game/_mygame/MetaHumans/BossUEFN"
ASSET_NAME = "SKM_Boss_UEFN"
ASSET_PATH = DESTINATION + "/" + ASSET_NAME
SKELETON_PATH = "/Game/_mygame/SK_UEFN_Mannequin.SK_UEFN_Mannequin"
REFERENCE_MESH_PATH = "/Game/_mygame/SKM_UEFN_Mannequin"
SOURCE_BODY_MESH_PATH = (
    "/Game/_mygame/MetaHumans/boss/Body/SKM_test_UEFNFit2_BodyMesh"
)
SOURCE_FACE_MESH_PATH = (
    "/Game/_mygame/MetaHumans/boss/Face/SKM_test_UEFNFit2_FaceMesh"
)
AUDIT = os.path.join(
    PROJECT,
    "Saved",
    "BlenderExchange",
    "BossUEFN",
    "Boss_UEFN_UnrealImportAudit.json",
)


def main():
    if not os.path.isfile(FBX):
        raise RuntimeError("Missing Boss FBX: " + FBX)
    skeleton = unreal.load_asset(SKELETON_PATH)
    if not isinstance(skeleton, unreal.Skeleton):
        raise RuntimeError("Missing UEFN Skeleton: " + SKELETON_PATH)
    reference_mesh = unreal.load_asset(REFERENCE_MESH_PATH)
    if not isinstance(reference_mesh, unreal.SkeletalMesh):
        raise RuntimeError("Missing UEFN reference mesh: " + REFERENCE_MESH_PATH)
    source_body = unreal.load_asset(SOURCE_BODY_MESH_PATH)
    source_face = unreal.load_asset(SOURCE_FACE_MESH_PATH)
    if not isinstance(source_body, unreal.SkeletalMesh):
        raise RuntimeError("Missing Boss source Body mesh: " + SOURCE_BODY_MESH_PATH)
    if not isinstance(source_face, unreal.SkeletalMesh):
        raise RuntimeError("Missing Boss source Face mesh: " + SOURCE_FACE_MESH_PATH)
    reference_modifier = unreal.SkeletonModifier()
    if not reference_modifier.set_skeletal_mesh(reference_mesh):
        raise RuntimeError("Could not inspect UEFN reference mesh skeleton")
    skeleton_names_before = [
        str(name) for name in reference_modifier.get_all_bone_names()
    ]
    # Blender represents the FBX top-level `root` joint as the Armature object,
    # so the clean Blender armature contains the remaining 87 bones. Unreal
    # restores that FBX node as the Skeleton's 88th/root bone on import.
    if len(skeleton_names_before) != 88:
        raise RuntimeError(
            "Unexpected UEFN Skeleton bone count: "
            + str(len(skeleton_names_before))
        )

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
    mesh_options = options.get_editor_property("skeletal_mesh_import_data")
    mesh_options.set_editor_property("import_morph_targets", False)
    mesh_options.set_editor_property("update_skeleton_reference_pose", False)
    mesh_options.set_editor_property("use_t0_as_ref_pose", False)
    mesh_options.set_editor_property(
        "normal_import_method",
        unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS,
    )

    task = unreal.AssetImportTask()
    task.set_editor_property("filename", FBX)
    task.set_editor_property("destination_path", DESTINATION)
    task.set_editor_property("destination_name", ASSET_NAME)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("replace_existing_settings", True)
    task.set_editor_property("options", options)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    imported = [str(path) for path in task.get_editor_property("imported_object_paths")]
    mesh = unreal.load_asset(ASSET_PATH)
    if not isinstance(mesh, unreal.SkeletalMesh):
        raise RuntimeError(
            "Boss import did not produce the expected Skeletal Mesh: "
            + str(imported)
        )
    assigned_skeleton = mesh.get_editor_property("skeleton")
    if assigned_skeleton is None or assigned_skeleton.get_path_name() != SKELETON_PATH:
        raise RuntimeError("Boss was not assigned to the existing UEFN Skeleton")

    reference_modifier_after = unreal.SkeletonModifier()
    if not reference_modifier_after.set_skeletal_mesh(reference_mesh):
        raise RuntimeError("Could not re-inspect UEFN reference mesh skeleton")
    skeleton_names_after = [
        str(name) for name in reference_modifier_after.get_all_bone_names()
    ]
    if skeleton_names_after != skeleton_names_before:
        raise RuntimeError("Boss import modified the shared UEFN Skeleton")

    skeleton_modifier = unreal.SkeletonModifier()
    if not skeleton_modifier.set_skeletal_mesh(mesh):
        raise RuntimeError("Could not inspect imported Boss skeleton")
    mesh_bones = [str(name) for name in skeleton_modifier.get_all_bone_names()]
    if mesh_bones != skeleton_names_before:
        raise RuntimeError("Imported Boss mesh reference skeleton differs from UEFN")

    # FBX carries stable polygon material regions/slot names.  Reuse the
    # already-assembled MetaHuman material instances rather than asking FBX to
    # create lossy basic materials.  The combined mesh contains Body plus the
    # seven used high-detail Face regions; Face LOD5-to-7 has no polygons.
    source_materials = [source_body.materials[0]] + list(source_face.materials[:7])
    if len(source_materials) != 8 or any(
        material.material_interface is None for material in source_materials
    ):
        raise RuntimeError("Boss source material payload is incomplete")
    mesh.set_editor_property("materials", source_materials)
    assigned_materials = [
        {
            "slot_name": str(material.material_slot_name),
            "asset": material.material_interface.get_path_name(),
        }
        for material in mesh.materials
    ]
    if len(assigned_materials) != 8:
        raise RuntimeError("Boss material assignment did not retain eight slots")

    skin_modifier = unreal.SkinWeightModifier()
    if not skin_modifier.set_skeletal_mesh(mesh):
        raise RuntimeError("Could not inspect imported Boss skin weights")
    vertices = skin_modifier.get_num_vertices()
    if vertices != 11331:
        raise RuntimeError("Unexpected imported Boss vertex count: " + str(vertices))

    unreal.EditorAssetLibrary.save_loaded_asset(mesh, only_if_is_dirty=False)
    bounds = mesh.get_bounds()
    report = {
        "fbx": FBX,
        "imported_object_paths": imported,
        "asset": mesh.get_path_name(),
        "skeleton": assigned_skeleton.get_path_name(),
        "shared_skeleton_unchanged": skeleton_names_after == skeleton_names_before,
        "mesh_bone_count": len(mesh_bones),
        "vertex_count": vertices,
        "materials": assigned_materials,
        "bounds_origin_cm": [
            bounds.origin.x,
            bounds.origin.y,
            bounds.origin.z,
        ],
        "bounds_extent_cm": [
            bounds.box_extent.x,
            bounds.box_extent.y,
            bounds.box_extent.z,
        ],
    }
    os.makedirs(os.path.dirname(AUDIT), exist_ok=True)
    with open(AUDIT, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    unreal.log("BOSS_UEFN_IMPORT=" + json.dumps(report, sort_keys=True))
    print("BOSS_UEFN_IMPORT=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
