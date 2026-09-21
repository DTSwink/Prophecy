import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'User PIE running; leave untouched.'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Debug.RefreshParryWithoutBlocker')
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
task=unreal.AssetExportTask();task.object=bp
task.filename=unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()+'Diagnostics/RemoveParryBlocker/After.copy')
task.automated=True;task.prompt=False;task.replace_identical=True
print('Exported refreshed Blueprint',unreal.Exporter.run_asset_export_task(task))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.Defense.PhysicalContactShapes+Prophecy.NN.Defense.ParryContacts+Prophecy.NN.Defense.ParryRecurrence')
