import os,pathlib,unreal
host=pathlib.Path(unreal.Paths.project_dir());out=host/'Saved/Diagnostics/SpearPike20261030'
assert os.getpid()==int((out/'editor.pid').read_text().strip())
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);assert not ed.get_game_world()
root=out.resolve().parents[2]
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Interchange.FeatureFlags.Import.FBX 0')
t=unreal.AssetImportTask();t.filename=str(root/'Exports/ImperialSpear/Unreal/SM_ImperialSpear.fbx');t.destination_path='/Game/_mygame/spear';t.destination_name='SM_ImperialSpear';t.automated=True;t.replace_existing=True;t.save=True
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t])
m=unreal.load_asset('/Game/_mygame/spear/SM_ImperialSpear');m.set_material(0,unreal.load_asset('/Game/_mygame/spear/M_ImperialSpear'));unreal.EditorAssetLibrary.save_loaded_asset(m,only_if_is_dirty=False)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.Spear')
print('Reimported corrected collision only; native tests queued.')
