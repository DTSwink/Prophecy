import os

import unreal

EXPORT_DIR = os.path.join(unreal.Paths.project_dir(), "Saved", "BlenderExchange")

EXPORTS = [
    ("/Game/MetaHumans/test/Body/SKM_test_BodyMesh", "Body_Original_MH.fbx"),
    ("/Game/MetaHumans/test/Face/SKM_test_FaceMesh", "Face_Original_MH.fbx"),
]

registry = unreal.AssetRegistryHelpers.get_asset_registry()
for data in registry.get_assets_by_path("/Game/MetaHumans/test", recursive=True):
    if str(data.asset_class_path.asset_name) == "SkeletalMesh":
        print("TEST_ASSET|{}".format(data.package_name))

for asset_path, filename in EXPORTS:
    asset = unreal.load_asset(asset_path)
    if asset is None:
        print("SKIP|{}".format(asset_path))
        continue
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
    size = os.path.getsize(os.path.join(EXPORT_DIR, filename)) if os.path.isfile(os.path.join(EXPORT_DIR, filename)) else -1
    print("EXPORT|{}|{}|ok={}|bytes={}".format(asset_path, filename, ok, size))
print("ORIGINAL_LIVE_EXPORT_DONE")
