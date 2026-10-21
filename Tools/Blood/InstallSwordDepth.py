"""Load the editor-only installer and preserve current A_Sword before its additive edit."""
import pathlib,sys,unreal,shutil
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'User Play is active; no changes made'
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SwordBloodDepth'
out.mkdir(parents=True,exist_ok=True)
bp=unreal.load_asset('/Game/_mygame/sword/A_Sword')
def export(name):
    t=unreal.AssetExportTask();t.object=bp;t.filename=str(out/name)
    t.exporter=unreal.ObjectExporterT3D();t.automated=True;t.prompt=False;t.replace_identical=True
    assert unreal.Exporter.run_asset_export_task(t)
if '--build' in sys.argv:
    export('before-build.txt')
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'LiveCoding.Compile')
    print('Editor helper build dispatched; no Blueprint edits yet')
else:
    export('before.txt')
    source=pathlib.Path(unreal.Paths.project_dir())/'Content/_mygame/sword/A_Sword.uasset'
    backup=out/'A_Sword.before.uasset'
    if not backup.exists():shutil.copy2(source,backup)
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Blood.InstallSwordDepth')
    export('after.txt')
    print('Installer called; inspect compile status and graph preservation before saving')
