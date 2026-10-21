import pathlib,shutil,sys,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SwordBloodDepth'
bp=unreal.load_asset('/Game/_mygame/sword/A_Sword')
def export(name):
    t=unreal.AssetExportTask();t.object=bp;t.filename=str(out/name);t.exporter=unreal.ObjectExporterT3D()
    t.automated=True;t.prompt=False;t.replace_identical=True
    assert unreal.Exporter.run_asset_export_task(t)
if '--build' in sys.argv:
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'LiveCoding.Compile')
    print('Dispatched minimal additive-stain build')
else:
    backup=out/'A_Sword.before-additive.uasset'
    if not backup.exists():shutil.copy2(pathlib.Path(unreal.Paths.project_content_dir())/'_mygame/sword/A_Sword.uasset',backup)
    if not (out/'before-additive.txt').exists():export('before-additive.txt')
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Blood.MakeSwordDepthAdditive')
    export('after-additive.txt')
    print('Additive upgrade installed, unsaved pending preservation/compile checks')
