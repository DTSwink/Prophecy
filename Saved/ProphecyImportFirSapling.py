import unreal

source_file = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy\SourceArt\PolyHaven\fir_sapling_1k\fir_sapling_1k.gltf"
destination_path = "/Game/Prophecy/External/PolyHaven/FirSapling"

task = unreal.AssetImportTask()
task.filename = source_file
task.destination_path = destination_path
task.automated = True
task.replace_existing = True
task.save = True

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
asset_tools.import_asset_tasks([task])

imported = list(task.imported_object_paths)
print("IMPORTED_OBJECTS", imported)

for object_path in imported:
    asset = unreal.load_asset(object_path)
    if isinstance(asset, unreal.StaticMesh):
        try:
            nanite_settings = asset.get_editor_property("nanite_settings")
            nanite_settings.enabled = True
            asset.set_editor_property("nanite_settings", nanite_settings)
            print("NANITE_ENABLED", object_path)
        except Exception as exc:
            print("NANITE_ENABLE_FAILED", object_path, exc)
        unreal.EditorAssetLibrary.save_loaded_asset(asset)

unreal.EditorAssetLibrary.save_directory(destination_path, only_if_is_dirty=False, recursive=True)
