import unreal,pathlib
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
task=unreal.AssetExportTask();task.object=bp;task.filename=str(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/DodgeMismatch/CurrentClampBP.copy');task.automated=True;task.prompt=False;task.replace_identical=True
print('EXPORT',unreal.Exporter.run_asset_export_task(task))
