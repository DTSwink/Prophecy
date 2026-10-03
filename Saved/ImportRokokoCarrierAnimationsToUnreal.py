import json
import os
import re

import unreal


SOURCE_DIR = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\RokokoCarrierFBX"
DESTINATION_PATH = "/Game/_mygame/Rokoko/FightAnimations_Carrier"


def sanitize_asset_name(filename):
    stem = os.path.splitext(os.path.basename(filename))[0]
    stem = re.sub(r"_Carrier$", "", stem)
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", stem).strip("_")
    return cleaned or "RokokoAnimation"


def safe_set(obj, property_name, value):
    try:
        obj.set_editor_property(property_name, value)
        return True
    except Exception:
        return False


def make_fbx_options(import_mesh, skeleton=None):
    options = unreal.FbxImportUI()
    safe_set(options, "automated_import_should_detect_type", False)
    safe_set(options, "mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
    safe_set(options, "import_as_skeletal", True)
    safe_set(options, "import_mesh", import_mesh)
    safe_set(options, "import_animations", True)
    safe_set(options, "create_physics_asset", False)
    safe_set(options, "import_materials", False)
    safe_set(options, "import_textures", False)
    if skeleton:
        safe_set(options, "skeleton", skeleton)

    try:
        mesh_data = options.get_editor_property("skeletal_mesh_import_data")
        safe_set(mesh_data, "import_meshes_in_bone_hierarchy", True)
        safe_set(mesh_data, "convert_scene", True)
        safe_set(mesh_data, "convert_scene_unit", True)
    except Exception:
        pass

    try:
        anim_data = options.get_editor_property("anim_sequence_import_data")
        safe_set(anim_data, "animation_length", unreal.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME)
        safe_set(anim_data, "remove_redundant_keys", False)
        safe_set(anim_data, "import_custom_attribute", True)
    except Exception:
        pass

    return options


def import_fbx(filename, destination_name, import_mesh, skeleton=None):
    task = unreal.AssetImportTask()
    task.filename = filename
    task.destination_path = DESTINATION_PATH
    task.destination_name = destination_name
    task.automated = True
    task.replace_existing = True
    task.save = True
    task.options = make_fbx_options(import_mesh=import_mesh, skeleton=skeleton)

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    imported_paths = list(task.imported_object_paths)
    imported_assets = [unreal.load_asset(path) for path in imported_paths]
    return imported_paths, imported_assets


def asset_type_name(asset):
    return asset.get_class().get_name() if asset else None


def find_skeleton(assets):
    for asset in assets:
        if isinstance(asset, unreal.Skeleton):
            return asset
    for asset in assets:
        if isinstance(asset, unreal.SkeletalMesh):
            try:
                skeleton = asset.get_editor_property("skeleton")
                if skeleton:
                    return skeleton
            except Exception:
                pass
    return None


def has_anim_sequence(assets):
    return any(isinstance(asset, unreal.AnimSequence) for asset in assets)


def main():
    try:
        unreal.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX 0")
    except Exception:
        pass

    fbx_files = sorted(
        os.path.join(SOURCE_DIR, name)
        for name in os.listdir(SOURCE_DIR)
        if name.lower().endswith(".fbx")
    )
    if not fbx_files:
        raise RuntimeError("No converted FBX files found in {}".format(SOURCE_DIR))

    unreal.EditorAssetLibrary.make_directory(DESTINATION_PATH)

    report = []
    skeleton = None

    for index, filename in enumerate(fbx_files):
        destination_name = sanitize_asset_name(filename)
        import_mesh = index == 0 or skeleton is None
        paths, assets = import_fbx(filename, destination_name, import_mesh=import_mesh, skeleton=skeleton)

        if not skeleton:
            skeleton = find_skeleton(assets)

        if not has_anim_sequence(assets) and skeleton and not import_mesh:
            paths, assets = import_fbx(filename, destination_name, import_mesh=True, skeleton=skeleton)

        report.append({
            "source": filename,
            "mode": "carrier_mesh_and_animation" if import_mesh else "animation_only_on_carrier_skeleton",
            "imported": [{"path": path, "type": asset_type_name(asset)} for path, asset in zip(paths, assets)],
            "skeleton": skeleton.get_path_name() if skeleton else None,
        })

    unreal.EditorAssetLibrary.save_directory(DESTINATION_PATH, only_if_is_dirty=False, recursive=True)
    print("ROKOKO_CARRIER_IMPORT_REPORT=" + json.dumps(report, indent=2))


main()
