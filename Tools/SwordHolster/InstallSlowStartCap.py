"""Build/install the narrow Slow Start graph correction; inspect before saving."""
import json, pathlib, shutil, sys, unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), "User Play left untouched"
root = pathlib.Path(unreal.Paths.project_dir()).resolve()
out = root / "Saved/Diagnostics/SceneClock"
bp = unreal.load_asset("/Game/_mygame/sword/A_Sword")
def export(name):
    task = unreal.AssetExportTask()
    task.object, task.filename = bp, str(out / (name + ".txt"))
    task.exporter = unreal.ObjectExporterT3D()
    task.automated, task.prompt, task.replace_identical = True, False, True
    assert unreal.Exporter.run_asset_export_task(task)
if "--build" in sys.argv:
    path = root / "Content/_mygame/sword/A_Sword.uasset"
    backup = out / "A_Sword.before-slow-cap.uasset"
    if not backup.exists(): shutil.copy2(path, backup)
    export("sword-before-build")
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), "LiveCoding.Compile")
    print("SLOW_START_BUILD_DISPATCHED")
else:
    export("sword-before-fix")
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),
        "Prophecy.Editor.RefreshHolsterGripPins SwordSlowStartFrameCap")
    export("sword-after-fix")
    print("SLOW_START_INSTALLED_UNSAVED")
