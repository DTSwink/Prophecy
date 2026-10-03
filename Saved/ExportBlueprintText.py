import os
import sys
import unreal


path = sys.argv[1]
asset = unreal.EditorAssetLibrary.load_asset(path)
if not asset:
    raise RuntimeError("Missing asset " + path)
output = os.path.join(unreal.Paths.project_saved_dir(), asset.get_name() + ".t3d")
task = unreal.AssetExportTask()
task.object = asset
task.filename = output
task.automated = True
task.prompt = False
task.replace_identical = True
task.exporter = unreal.ObjectExporterT3D()
success = unreal.Exporter.run_asset_export_task(task)
print("EXPORTED success={} output={}".format(success, output))
