import unreal,pathlib
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
t=unreal.AssetExportTask();t.object=bp;t.filename=str(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/Pin529BP.copy');t.automated=True;t.prompt=False;t.replace_identical=True
print('export',unreal.Exporter.run_asset_export_task(t))
