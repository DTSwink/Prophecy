import json
import os
import re

import unreal


SOURCE_DIR = r"C:\Users\singerie\AppData\LocalLow\Rokoko Electronics\Rokoko Studio\MotionLibrary"
DESTINATION_PATH = "/Game/_mygame/Rokoko/FightAnimations_Original"


def sanitize_asset_name(filename):
    stem = os.path.splitext(os.path.basename(filename))[0]
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
        raise RuntimeError("No FBX files found in {}".format(SOURCE_DIR))

    unreal.EditorAssetLibrary.make_directory(DESTINATION_PATH)

    report = []
    skeleton = None

    first_file = fbx_files[0]
    first_name = sanitize_asset_name(first_file)
    first_paths, first_assets = import_fbx(first_file, first_name, import_mesh=True)
    skeleton = find_skeleton(first_assets)
    report.append({
        "source": first_file,
        "mode": "skeletal_mesh_and_animation",
        "imported": [{"path": path, "type": asset_type_name(asset)} for path, asset in zip(first_paths, first_assets)],
        "skeleton": skeleton.get_path_name() if skeleton else None,
    })

    for filename in fbx_files[1:]:
        destination_name = sanitize_asset_name(filename)
        paths, assets = import_fbx(filename, destination_name, import_mesh=False, skeleton=skeleton)

        mode = "animation_only"
        if not has_anim_sequence(assets):
            paths, assets = import_fbx(filename, destination_name, import_mesh=True)
            mode = "fallback_skeletal_mesh_and_animation"
            if not skeleton:
                skeleton = find_skeleton(assets)

        report.append({
            "source": filename,
            "mode": mode,
            "imported": [{"path": path, "type": asset_type_name(asset)} for path, asset in zip(paths, assets)],
            "skeleton": skeleton.get_path_name() if skeleton else None,
        })

    unreal.EditorAssetLibrary.save_directory(DESTINATION_PATH, only_if_is_dirty=False, recursive=True)
    print("PROPHECY_ROKOKO_IMPORT_REPORT=" + json.dumps(report, indent=2))


main()
