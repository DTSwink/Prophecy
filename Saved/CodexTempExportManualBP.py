import unreal


asset = unreal.EditorAssetLibrary.load_asset("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent")
task = unreal.AssetExportTask()
task.object = asset
task.filename = unreal.Paths.convert_relative_path_to_full(
    unreal.Paths.project_saved_dir() + "BP_ProphecyManualPoseAgent.copy")
task.automated = True
task.prompt = False
task.replace_identical = True
print("BP_EXPORT", unreal.Exporter.run_asset_export_task(task), task.filename)
