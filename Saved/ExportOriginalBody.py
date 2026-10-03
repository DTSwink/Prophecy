import os

import unreal

EXPORT_DIR = os.path.join(unreal.Paths.project_dir(), "Saved", "BlenderExchange")
os.makedirs(EXPORT_DIR, exist_ok=True)

registry = unreal.AssetRegistryHelpers.get_asset_registry()

candidates = []
for root in ("/Game/MetaHumans/test", "/Game/MetaHumans/test_UEFNExactFull",
             "/Game/_mygame/MetaHumans"):
    for data in registry.get_assets_by_path(root, recursive=True):
        if str(data.asset_class_path.asset_name) == "SkeletalMesh":
            path = str(data.package_name)
            lower = path.lower()
            if "body" in lower or "carrier" in lower:
                candidates.append(path)
                print("CANDIDATE|{}".format(path))


def export_fbx(asset_path, filename):
    asset = unreal.load_asset(asset_path)
    if asset is None:
        print("EXPORT_SKIP|{}".format(asset_path))
        return
    options = unreal.FbxExportOption()
    options.set_editor_property("ascii", False)
    options.set_editor_property("collision", False)
    options.set_editor_property("level_of_detail", False)
    options.set_editor_property("export_morph_targets", False)
    options.set_editor_property("vertex_color", False)
    task = unreal.AssetExportTask()
    task.set_editor_property("object", asset)
    task.set_editor_property("filename", os.path.join(EXPORT_DIR, filename))
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_identical", True)
    task.set_editor_property("prompt", False)
    task.set_editor_property("options", options)
    ok = unreal.Exporter.run_asset_export_task(task)
    print("EXPORT|{}|{}|ok={}|errors={}".format(
        asset_path, filename, ok, list(task.get_editor_property("errors"))))


for path in candidates:
    safe = path.replace("/Game/", "").replace("/", "__")
    export_fbx(path, "Candidate__{}.fbx".format(safe))

print("ORIGINAL_EXPORT_DONE")
